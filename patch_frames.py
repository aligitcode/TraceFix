from pathlib import Path

p = Path("src/tracefix/main.py")
t = p.read_text(encoding="utf-8")
old = '''    out = []
    for frame in frames[:-1]:
        ctx = get_code_context(frame["file"], int(frame["line"]), radius)
        if ctx:'''
new = '''    out = []
    seen = set()
    failing_file = str(Path(frames[-1]["file"]).resolve()) if frames else ""
    for frame in frames[:-1]:
        resolved = str(Path(frame["file"]).resolve())
        key = (resolved, frame["line"])
        if resolved == failing_file or key in seen:
            continue
        seen.add(key)
        ctx = get_code_context(frame["file"], int(frame["line"]), radius)
        if ctx:'''
assert old in t
p.write_text(t.replace(old, new), encoding="utf-8")
print("patched")
