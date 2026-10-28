import subprocess, sys
from pathlib import Path
from tracefix.investigator import build_prompt
from tracefix.main import (find_called_definitions, find_imported_constants,
                           get_code_context, get_frame_contexts, parse_frames, summarize_error)

n = sys.argv[1] if len(sys.argv) > 1 else "11"
run = subprocess.run([sys.executable, f"examples/buggy_shop/run_bug{n}.py"], capture_output=True, text=True)
frames = parse_frames(run.stderr)
failing = frames[-1]
summary = summarize_error(run.stderr)
context = get_code_context(failing["file"], int(failing["line"]))
fp = Path(failing["file"]).resolve()
defs = [d for d in find_called_definitions(context, str(fp.parent)) if Path(d["file"]).resolve() != fp]
defs = defs + [{"file": f["file"], "lines": f["lines"]} for f in get_frame_contexts(frames)] + find_imported_constants(failing["file"])
prompt = build_prompt(summary, failing, context, defs or None)
print(prompt)
print("\n--- characters:", len(prompt), " words:", len(prompt.split()))
