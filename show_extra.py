import json, subprocess, sys
from pathlib import Path
from tracefix.main import find_imported_constants, get_frame_contexts, parse_frames

for case in json.loads(Path("examples/expected.json").read_text(encoding="utf-8")):
    run = subprocess.run([sys.executable, case["script"]], capture_output=True, text=True)
    frames = parse_frames(run.stderr)
    fc = get_frame_contexts(frames)
    ic = find_imported_constants(frames[-1]["file"])
    print(Path(case["script"]).name, "extra frames:", [Path(f["file"]).name for f in fc], "constants:", [Path(c["file"]).name for c in ic])
