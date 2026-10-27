from pathlib import Path

p = Path("evaluate.py")
t = p.read_text(encoding="utf-8")
t = t.replace("    find_called_definitions,\n", "    find_called_definitions,\n    find_imported_constants,\n    get_frame_contexts,\n", 1)
old = '        row["extra_functions"] = [d["name"] for d in definitions]\n'
new = '''        row["extra_functions"] = [d["name"] for d in definitions]
        definitions = definitions + [
            {"file": f["file"], "lines": f["lines"]} for f in get_frame_contexts(frames)
        ] + find_imported_constants(failing["file"])
        row["extra_evidence_files"] = sorted({Path(d["file"]).name for d in definitions})
'''
assert old in t
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")

q = Path("src/tracefix/investigator.py")
s = q.read_text(encoding="utf-8")
old2 = '"Code of functions called near the failure (file:line: code):\\n"'
new2 = '"Additional code evidence: functions called near the failure, other traceback frames, imported constants (file:line: code):\\n"'
assert old2 in s
s = s.replace(old2, new2, 1)
s = s.replace("lines of the functions above", "lines of the additional evidence above", 1)
q.write_text(s, encoding="utf-8")
print("patched")
