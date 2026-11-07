import json

from tracefix import compare


def write(tmp_path, name, meta, rows):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"meta": meta, "rows": rows}), encoding="utf-8")
    return str(path)


def test_table_marks_wrong_false_confidence_and_missing(tmp_path):
    a = write(tmp_path, "old", {"model": "m", "commit": "c1"}, [
        {"bug": "run_bug10.py", "correct_behavior": False, "confidence": "high", "false_confidence": True},
        {"bug": "run_bug2.py", "correct_behavior": True, "confidence": "high", "false_confidence": False},
    ])
    b = write(tmp_path, "new", {"model": "m", "commit": "c2", "mode": "baseline"}, [
        {"bug": "run_bug10.py", "correct_behavior": True, "confidence": "low"},
        {"bug": "run_bug2.py", "llm_error": "503 UNAVAILABLE"},
    ])
    out = compare.table([compare.load(a), compare.load(b)])
    lines = out.splitlines()
    assert lines[0] == "| bug | old | new |"
    assert lines[2].startswith("| run_bug2.py | ok (high) | - |")          # numeric order: 2 before 10
    assert "| run_bug10.py | WRONG (high) FALSE-CONF | ok (low) |" in out
    assert "| old | m | tracefix | c1 | 2 / 2 | 1 / 2 | 1 |" in out
    assert "| new | m | baseline | c2 | 1 / 2 | 1 / 1 | 0 |" in out         # an error is "no answer", not "wrong"


def test_old_result_files_without_new_fields_still_load(tmp_path):
    old = write(tmp_path, "before", {}, [{"bug": "run_bug1.py", "correct_behavior": True, "confidence": "high"}])
    assert "ok (high)" in compare.table([compare.load(old)])
