import subprocess
import sys

from tracefix.main import summarize_error

result = subprocess.run(
    [sys.executable, "examples/buggy_shop/run_bug1.py"],
    capture_output=True,
    text=True,
)

print("Raw error text:")
print(result.stderr)
print("TraceFix summary:")
print(summarize_error(result.stderr))