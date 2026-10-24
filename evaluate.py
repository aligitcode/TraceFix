import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from tracefix.investigator import ask_gemini, build_prompt
from tracefix.main import get_code_context, parse_frames, summarize_error
from tracefix.verifier import verify_report

load_dotenv()
use_llm = "--no-llm" not in sys.argv
cases = json.loads(Path("examples/expected.json").read_text(encoding="utf-8"))

commit = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
).stdout.strip()
meta = {
    "commit": commit,
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
    sufficient = case.get("evidence_sufficient", True)
    row["evidence_sufficient"] = sufficient

    if use_llm:
        context = get_code_context(failing["file"], int(failing["line"]))
        try:
            answer = ask_gemini(build_prompt(summary, failing, context))
            verification = verify_report(answer, context)
            cited = answer.get("evidence_lines", [])
            if not isinstance(cited, list):
                cited = []
            confidence = answer.get("confidence")
            cites_cause = (
                Path(failing["file"]).name == case["cause_file"]
                and case["cause_line"] in cited
            )
            if sufficient:
                correct = cites_cause
            else:
                correct = confidence in ("low", "inconclusive")
            row["status"] = verification["status"]
            row["confidence"] = confidence
            row["cites_cause_line"] = cites_cause
            row["correct_behavior"] = correct
            row["false_confidence"] = verification["status"] == "supported" and not correct
        except Exception as error:
            row["llm_error"] = str(error)[:200]
        time.sleep(4)

    rows.append(row)

total = len(rows)
print(f"commit={meta['commit']}  model={meta['model']}  llm={meta['llm']}")
for row in rows:
    print(row)

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

Path("results").mkdir(exist_ok=True)
Path("results/latest.json").write_text(
    json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8"
)
print("Saved to results/latest.json")
