import subprocess
import sys

from tracefix.main import summarize_error, parse_frames, get_code_context

script = sys.argv[1] if len(sys.argv) > 1 else "examples/buggy_shop/run_bug1.py"

result = subprocess.run(
    [sys.executable, script],
    capture_output=True,
    text=True,
)

print("Raw error text:")
print(result.stderr)
print("TraceFix summary:")
print(summarize_error(result.stderr))

frames = parse_frames(result.stderr)
print("Frames:")
print(frames)

if frames:
    failing = frames[-1]
    print("Code around the failure:")
    for item in get_code_context(failing["file"], int(failing["line"])):
        print(item["line"], item["text"])
else:
    print("No traceback found. The script may have run without errors.")