import subprocess
import sys

from tracefix.main import summarize_error, parse_frames, get_code_context

result = subprocess.run(
    [sys.executable, "examples/buggy_shop/run_bug1.py"],
    capture_output=True,
    text=True,
)

print("Raw error text:")
print(result.stderr)
print("TraceFix summary:")
print(summarize_error(result.stderr))
print("Frames:")
print(parse_frames(result.stderr))

failing = parse_frames(result.stderr)[-1]
print("Code around the failure:")
for item in get_code_context(failing["file"], int(failing["line"])):
    print(item["line"], item["text"])