import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from tracefix.investigator import ask_gemini, build_prompt
from tracefix.main import get_code_context, parse_frames, summarize_error
from tracefix.scoring import score_answer
from tracefix.verifier import verify_report

load_dotenv()
use_llm = "--no-llm" not in sys.argv
cases = json.loads(Path("examples/expected.json").read_text(encoding="utf-8"))


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


meta = {
    "commit": git("rev-parse", "--short", "HEAD"),
    "uncommitted_changes": bool(git("status", "--porcelain")),
    "model": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
    "llm": use_llm,
}

rows = []
for case in cases:
    run = subprocess.run(
        [sys.executable, case["script"]], capture_output=True, text=True
    )
    frames = parse_frames(run.stderr)
    row = {"bug": Path(case["script"]).name}

    if not frames:
        row.update(error_ok=False, file_ok=False, line_ok=False)
        rows.append(row)
        continue

    summary = summarize_error(run.stderr)
    failing = frames[-1]
    row["error_ok"] = summary["error_type"] == case["error_type"]
    row["file_ok"] = Path(failing["file"]).name == case["file"]
    row["line_ok"] = int(failing["line"]) == case["line"]
    row["evidence_sufficient"] = case.get("evidence_sufficient", True)

    if use_llm:
        context = get_code_context(failing["file"], int(failing["line"]))
        try:
            answer = ask_gemini(build_prompt(summary, failing, context))
            verification = verify_report(answer, context)
            row.update(score_answer(answer, verification, case, failing["file"]))
            row["likely_cause"] = answer.get("likely_cause")
        except Exception as error:
            row["llm_error"] = str(error)[:200]
        time.sleep(4)

    rows.append(row)

total = len(rows)
print(
    f"commit={meta['commit']}  uncommitted_changes={meta['uncommitted_changes']}  "
    f"model={meta['model']}  llm={meta['llm']}"
)
for row in rows:
    print({k: v for k, v in row.items() if k != "likely_cause"})

parsing_ok = sum(1 for r in rows if r["error_ok"] and r["file_ok"] and r["line_ok"])
print()
print(f"Parsing correct (error, file, line): {parsing_ok}/{total}")

if use_llm:
    answered = [r for r in rows if "llm_error" not in r]
    failed = total - len(answered)
    correct = sum(1 for r in answered if r.get("correct_behavior"))
    false_conf = sum(1 for r in answered if r.get("false_confidence"))
    easy = [r for r in answered if r.get("evidence_sufficient")]
    hard = [r for r in answered if not r.get("evidence_sufficient")]
    print(f"Gemini calls that failed (not scored): {failed}/{total}")
    print(f"Correct behavior: {correct}/{len(answered)}")
    print(f"  cases with enough evidence: {sum(1 for r in easy if r.get('correct_behavior'))}/{len(easy)}")
    print(f"  cases that should be low or inconclusive: {sum(1 for r in hard if r.get('correct_behavior'))}/{len(hard)}")
    print(f"Verifier said supported but behavior was wrong: {false_conf}/{len(answered)}")
    print("Read each likely_cause in results/latest.json yourself: the score checks cited lines, not the explanation.")

Path("results").mkdir(exist_ok=True)
Path("results/latest.json").write_text(
    json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8"
)
print("Saved to results/latest.json")
