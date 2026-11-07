"""Run TraceFix on every benchmark bug and score it.

    python evaluate.py --no-llm      offline checks only (traceback parsing, evidence); sends no request
    python evaluate.py               ask Gemini; answers are saved, so nothing is ever asked twice
    python evaluate.py --save-as results/after_evidence.json
                                     also keep a copy, but only when every bug has an answer
    python evaluate.py --cache-only  never send a request; rebuild the result from saved answers
    python evaluate.py --baseline    the plain-chatbot baseline: traceback + failing file only
    python evaluate.py --cases examples/expected_heldout.json
                                     run a different answer key (the fresh bugs)
    python evaluate.py --only 11,12  run just these bug numbers

Why it is built this way: the free Gemini tier allows about 20 requests per day per model,
and a request that fails with 503 or 504 still seems to use one (docs/gemini_quota_notes.md).
So the run reuses saved answers first, paces its requests, backs off, stops when Gemini is
clearly overloaded, and never sends more than --max-requests.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from tracefix.baseline import baseline_evidence, build_baseline_prompt
from tracefix.investigator import LAST_CALL, ask_gemini, build_prompt, get_cached, model_name
from tracefix.main import (
    find_called_definitions,
    find_imported_constants,
    get_code_context,
    get_frame_contexts,
    parse_frames,
    summarize_error,
)
from tracefix.resilience import CallFailed, CallGuard, GeminiError, RetryPolicy
from tracefix.runner import run_pending
from tracefix.scoring import evidence_covers, score_answer
from tracefix.verifier import verify_report

STOP_ADVICE = {
    "daily_quota": (
        "Google says the daily free-tier limit for this model is used up. It resets at midnight "
        "Pacific time (about 10:00 in Cairo). Answers so far are saved in results/cache, so the "
        "next run only asks for the missing bugs."
    ),
    "budget": (
        "The request limit (--max-requests) was reached. Run the same command again to continue; "
        "saved answers are reused."
    ),
    "unavailable": (
        "Gemini stayed overloaded or timed out, so the run stopped instead of wasting requests. "
        "Run the same command again later; saved answers are reused."
    ),
    "fatal": (
        "Gemini rejected the key, the model name or the region. Fix that first (see the error in "
        "results/latest.json); no further requests were sent."
    ),
    "interrupted": "The run was interrupted. Saved answers are reused next time.",
    "cache_only": "Nothing was asked (--cache-only). Run again without it to ask for the missing bugs.",
}

DEFAULT_CASES = "examples/expected.json"


@dataclass
class Item:
    case: dict
    row: dict
    failing: dict | None = None
    context: list = field(default_factory=list)
    definitions: list = field(default_factory=list)
    summary: dict | None = None
    prompt: str = ""

    @property
    def name(self) -> str:
        return self.row["bug"]


def git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Run TraceFix on every benchmark bug and score it.")
    p.add_argument("--no-llm", action="store_true", help="offline checks only; send no request")
    p.add_argument("--max-requests", type=int, default=20,
                   help="most requests this run may send, failed ones included (0 = no limit)")
    p.add_argument("--attempts", type=int, default=2, help="tries per bug per pass")
    p.add_argument("--passes", type=int, default=3, help="how many times to go back to unanswered bugs")
    p.add_argument("--pass-wait", type=float, default=600.0, help="seconds to wait between passes")
    p.add_argument("--breaker", type=int, default=3,
                   help="stop the pass after this many failed requests in a row")
    p.add_argument("--backoff-base", type=float, default=20.0, help="first retry wait in seconds, doubles each time")
    p.add_argument("--min-interval", type=float, default=13.0, help="minimum seconds between two requests")
    p.add_argument("--save-as", help="copy the result here, only if every bug was answered")
    p.add_argument("--cases", default=DEFAULT_CASES, help="answer key to run (default: the 14 original bugs)")
    p.add_argument("--only", help="comma-separated bug numbers to run, for example 11,12,13")
    p.add_argument("--cache-only", action="store_true", help="send no request; use saved answers only")
    p.add_argument("--baseline", action="store_true",
                   help="plain-chatbot baseline: traceback + failing file only, same model and scoring")
    return p.parse_args(argv)


def bug_number(case: dict):
    found = re.search(r"run_bug(\d+)\.py$", case["script"])
    return int(found.group(1)) if found else None


def result_name(args, use_llm: bool) -> str:
    """Different runs get different file names, so one can never overwrite another."""
    name = "latest"
    if args.baseline:
        name += "_baseline"
    if args.cases != DEFAULT_CASES:
        name += "_" + Path(args.cases).stem.replace("expected_", "")
    if not use_llm:
        name += "_no_llm"
    return name + ".json"


def prepare(case: dict, baseline: bool = False) -> Item:
    """Run one buggy script and build everything the prompt needs. Sends no request."""
    try:
        run = subprocess.run(
            [sys.executable, case["script"]], capture_output=True, text=True, timeout=60
        )
        stderr = run.stderr
    except subprocess.TimeoutExpired:
        stderr = ""
    frames = parse_frames(stderr)
    row = {"bug": Path(case["script"]).name}

    if not frames:
        row.update(error_ok=False, file_ok=False, line_ok=False)
        return Item(case, row)

    summary = summarize_error(stderr)
    failing = frames[-1]
    row["error_ok"] = summary["error_type"] == case["error_type"]
    row["file_ok"] = Path(failing["file"]).name == case["file"]
    row["line_ok"] = int(failing["line"]) == case["line"]
    row["evidence_sufficient"] = case.get("evidence_sufficient", True)

    if baseline:
        # What a developer would paste into a chatbot. Whether that is enough to find the
        # cause is decided from the evidence itself, not copied from the TraceFix answer key.
        context, definitions = baseline_evidence(frames)
        sufficient = evidence_covers(case, failing["file"], context, definitions)
        case = {**case, "evidence_sufficient": sufficient}
        row["evidence_sufficient"] = sufficient
        row["cause_in_evidence"] = sufficient
        row["extra_functions"] = []
        row["extra_evidence_files"] = sorted({Path(d["file"]).name for d in definitions})
        prompt = build_baseline_prompt(stderr, failing, context)
        return Item(case, row, failing, context, definitions, summary, prompt)

    context = get_code_context(failing["file"], int(failing["line"]))
    failing_path = Path(failing["file"]).resolve()
    definitions = [
        d
        for d in find_called_definitions(context, str(failing_path.parent))
        if Path(d["file"]).resolve() != failing_path
    ]
    row["extra_functions"] = [d["name"] for d in definitions]
    definitions = definitions + [
        {"file": f["file"], "lines": f["lines"]} for f in get_frame_contexts(frames)
    ] + find_imported_constants(failing["file"])
    row["extra_evidence_files"] = sorted({Path(d["file"]).name for d in definitions})
    row["cause_in_evidence"] = evidence_covers(case, failing["file"], context, definitions)

    prompt = build_prompt(summary, failing, context, definitions or None)
    return Item(case, row, failing, context, definitions, summary, prompt)


def finish_row(item: Item, answer: dict):
    verification = verify_report(answer, item.context, item.definitions or None, item.failing["file"])
    item.row.update(score_answer(answer, verification, item.case, item.failing["file"]))
    item.row["likely_cause"] = answer.get("likely_cause")
    item.row["evidence_lines"] = answer.get("evidence_lines")


def ask_all(items, args):
    """Fill in the Gemini part of every row. Returns (run result or None, cache hits, guard)."""
    cache_hits = 0
    todo = []
    for item in items:
        if item.failing is None:
            item.row["llm_error"] = "not asked: the script produced no traceback"
            continue
        cached = get_cached(item.prompt)  # saved answers first: they cost nothing
        if cached is None:
            todo.append(item)
        else:
            finish_row(item, cached)
            cache_hits += 1

    guard = CallGuard(
        policy=RetryPolicy(attempts=args.attempts, backoff_base=args.backoff_base),
        max_requests=args.max_requests,
        breaker_threshold=args.breaker,
        min_interval=args.min_interval,
    )
    if args.cache_only:
        for item in todo:
            item.row["llm_error"] = "not asked: --cache-only and there is no saved answer for this prompt"
        print(
            f"Cache only: {cache_hits} saved answer(s) reused, {len(todo)} bug(s) have none. "
            "No request was sent.",
            flush=True,
        )
        return None, cache_hits, guard

    print(
        f"Gemini model {model_name()}: {len(todo)} bug(s) need an answer, {cache_hits} already saved. "
        f"Request limit {args.max_requests or 'none'}, at least {args.min_interval:g}s between requests.",
        flush=True,
    )
    if not todo:
        return None, cache_hits, guard

    done = 0

    def ask_one(item):
        nonlocal done
        print(f"[{done + 1}/{len(todo)}] {item.name}: asking Gemini", flush=True)
        try:
            answer = ask_gemini(item.prompt, guard=guard)
            try:
                finish_row(item, answer)
            except Exception as error:  # the answer is saved; the scoring code failed
                raise CallFailed(f"scoring failed: {type(error).__name__}: {error}", retryable=False) from error
            done += 1
        except GeminiError:
            raise
        except Exception as error:
            raise CallFailed(f"unexpected error: {type(error).__name__}: {error}", retryable=False) from error
        finally:
            if LAST_CALL["requests"]:
                item.row["api_requests"] = item.row.get("api_requests", 0) + LAST_CALL["requests"]
                item.row.setdefault("attempts", []).extend(LAST_CALL["attempts"])

    outcome = run_pending(todo, ask_one, guard, passes=args.passes, pass_wait=args.pass_wait)
    for item in todo:
        if item.name in outcome.unanswered:
            item.row["llm_error"] = outcome.errors.get(item.name, "not answered")[:300]
    return outcome, cache_hits, guard


def main(argv=None) -> int:
    args = parse_args(argv)
    load_dotenv()
    use_llm = not args.no_llm
    results_dir = Path(os.environ.get("TRACEFIX_RESULTS_DIR", "results"))
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        wanted = {int(n) for n in args.only.split(",") if n.strip()}
        cases = [c for c in cases if bug_number(c) in wanted]
        if not cases:
            print(f"--only {args.only}: no bug in {args.cases} has one of those numbers.")
            return 2

    meta = {
        "commit": git("rev-parse", "--short", "HEAD"),
        "uncommitted_changes": bool(git("status", "--porcelain")),
        "model": model_name(),
        "llm": use_llm,
        "mode": "baseline" if args.baseline else "tracefix",
        "cases": args.cases,
    }

    items = [prepare(case, args.baseline) for case in cases]
    rows = [item.row for item in items]
    outcome, cache_hits, guard = (ask_all(items, args) if use_llm else (None, 0, None))

    total = len(rows)
    answered = [r for r in rows if "llm_error" not in r]
    complete = use_llm and len(answered) == total
    if use_llm:
        meta.update(
            requests_sent=guard.requests,
            answers_from_cache=cache_hits,
            complete=complete,
            stop_reason=outcome.stop_reason if outcome else None,
        )

    print(
        f"commit={meta['commit']}  uncommitted_changes={meta['uncommitted_changes']}  "
        f"model={meta['model']}  llm={meta['llm']}"
    )
    for row in rows:
        print({k: v for k, v in row.items() if k not in ("likely_cause", "evidence_lines", "attempts")})

    parsing_ok = sum(1 for r in rows if r["error_ok"] and r["file_ok"] and r["line_ok"])
    with_evidence = [r for r in rows if "cause_in_evidence" in r]
    print()
    print(f"Parsing correct (error, file, line): {parsing_ok}/{total}")
    print(f"Evidence contains the cause line: {sum(1 for r in with_evidence if r['cause_in_evidence'])}/{len(with_evidence)}")

    if use_llm:
        failed = total - len(answered)
        correct = sum(1 for r in answered if r.get("correct_behavior"))
        false_conf = sum(1 for r in answered if r.get("false_confidence"))
        easy = [r for r in answered if r.get("evidence_sufficient")]
        hard = [r for r in answered if not r.get("evidence_sufficient")]
        new_answers = len(outcome.answered) if outcome else 0
        print(f"Gemini calls that failed (not scored): {failed}/{total}")
        print(
            f"API requests made: {guard.requests} ({new_answers} answered, {guard.requests - new_answers} failed)"
            f"   answers from cache: {cache_hits}"
        )
        print(f"Correct behavior: {correct}/{len(answered)}")
        print(f"  cases with enough evidence: {sum(1 for r in easy if r.get('correct_behavior'))}/{len(easy)}")
        print(f"  cases that should be low or inconclusive: {sum(1 for r in hard if r.get('correct_behavior'))}/{len(hard)}")
        print(f"Verifier said supported but behavior was wrong: {false_conf}/{len(answered)}")
        print("Read each likely_cause in results/latest.json yourself: the score checks cited lines, not the explanation.")
        if complete:
            print("COMPLETE: every bug has an answer.")
        else:
            print()
            print("Bugs without an answer: " + ", ".join(r["bug"] for r in rows if "llm_error" in r))
            reason = "cache_only" if args.cache_only else (outcome.stop_reason if outcome else None)
            print(STOP_ADVICE.get(reason, "Some bugs failed with errors that retrying cannot fix; see llm_error in the saved result file."))

    results_dir.mkdir(parents=True, exist_ok=True)
    latest = results_dir / result_name(args, use_llm)
    payload = json.dumps({"meta": meta, "rows": rows}, indent=2)
    latest.write_text(payload, encoding="utf-8")
    print(f"Saved to {latest.as_posix()}")

    if args.save_as:
        if complete:
            target = Path(args.save_as)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
            print(f"Saved a copy to {target.as_posix()}")
        else:
            print(f"NOT saved to {args.save_as}: the run is not complete (--save-as only keeps complete runs).")

    return 0 if (not use_llm or complete) else 1


if __name__ == "__main__":
    sys.exit(main())
