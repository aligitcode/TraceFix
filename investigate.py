import json
import subprocess
import sys

from tracefix.investigator import ask_gemini, build_prompt
from tracefix.main import get_code_context, parse_frames, summarize_error
from tracefix.verifier import verify_report

script = sys.argv[1] if len(sys.argv) > 1 else "examples/buggy_shop/run_bug1.py"

result = subprocess.run(
    [sys.executable, script],
    capture_output=True,
    text=True,
)

frames = parse_frames(result.stderr)
if not frames:
    print("No traceback found. The script may have run without errors.")
    sys.exit()

summary = summarize_error(result.stderr)
failing = frames[-1]
context = get_code_context(failing["file"], int(failing["line"]))

prompt = build_prompt(summary, failing, context)
answer = ask_gemini(prompt)
verification = verify_report(answer, context)

print(json.dumps({"report": answer, "verification": verification}, indent=2))
