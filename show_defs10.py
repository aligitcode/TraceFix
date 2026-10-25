import subprocess, sys
from pathlib import Path
from tracefix.main import find_called_definitions, get_code_context, parse_frames

run = subprocess.run([sys.executable, "examples/buggy_shop/run_bug10.py"], capture_output=True, text=True)
failing = parse_frames(run.stderr)[-1]
context = get_code_context(failing["file"], int(failing["line"]))
for d in find_called_definitions(context, str(Path(failing["file"]).parent)):
    print(d["name"], d["file"], d["start"], d["end"])
    for l in d["lines"]:
        print(l["line"], l["text"])
