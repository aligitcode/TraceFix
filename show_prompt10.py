import subprocess, sys
from tracefix.investigator import build_prompt
from tracefix.main import get_code_context, parse_frames, summarize_error

run = subprocess.run([sys.executable, "examples/buggy_shop/run_bug10.py"], capture_output=True, text=True)
frames = parse_frames(run.stderr)
failing = frames[-1]
summary = summarize_error(run.stderr)
context = get_code_context(failing["file"], int(failing["line"]))
print(build_prompt(summary, failing, context))
