import json
import subprocess
import sys
import time
from pathlib import Path

from tracefix.investigator import ask_gemini, build_prompt
from tracefix.main import get_code_context, parse_frames, summarize_error
from tracefix.verifier import verify_report

use_llm = "--no-llm" not in sys.argv
cases = json.loads(Path("examples/expected.json").read_text(encoding="utf-8"))

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

    if use_llm:
        context = get_code_context(failing["file"], int(failing["line"]))
        try:
            answer = ask_gemini(build_prompt(summary, failing, context))
            verification = verify_report(answer, context)
            cited = answer.get("evidence_lines", [])
            row["status"] = verification["status"]
            row["confidence"] = answer.get("confidence")
            row["cites_failing_line"] = isinstance(cited, list) and case["line"] in cited
        except Exception as error:
            row["llm_error"] = str(error)[:120]
        time.sleep(4)

    rows.append(row)

total = len(rows)
for row in rows:
    print(row)

parsing_ok = sum(1 for r in rows if r["error_ok"] and r["file_ok"] and r["line_ok"])
print()
print(f"Parsing correct (error, file, line): {parsing_ok}/{total}")

if use_llm:
    supported = sum(1 for r in rows if r.get("status") == "supported")
    cites = sum(1 for r in rows if r.get("cites_failing_line"))
    failed = sum(1 for r in rows if "llm_error" in r)
    print(f"Gemini cites the failing line: {cites}/{total}")
    print(f"Verifier says supported: {supported}/{total}")
    print(f"Gemini calls that failed: {failed}/{total}")

Path("results").mkdir(exist_ok=True)
Path("results/latest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("Saved to results/latest.json")
