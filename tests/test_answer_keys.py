"""The answer keys decide what counts as correct, so they get tests too (offline, no Gemini).

For every case: the script fails the way the key says, the cause line exists, and
`evidence_sufficient` agrees with what the retrieval step really collects. That last rule is how
the label is defined: "sufficient" means the cause line is inside the evidence sent to the model.
"""

import json
from pathlib import Path

import pytest

import evaluate

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["examples/expected.json", "examples/expected_heldout.json"]


def all_cases():
    return [
        pytest.param(case, id=Path(case["script"]).name)
        for key in KEYS
        for case in json.loads((ROOT / key).read_text(encoding="utf-8"))
    ]


@pytest.fixture(autouse=True)
def from_repo_root(monkeypatch):
    monkeypatch.chdir(ROOT)


@pytest.mark.parametrize("case", all_cases())
def test_key_matches_the_real_failure_and_the_real_retrieval(case):
    item = evaluate.prepare(case)
    row = item.row
    assert (row["error_ok"], row["file_ok"], row["line_ok"]) == (True, True, True), row

    cause = ROOT / Path(case["script"]).parent / case["cause_file"]
    assert cause.is_file(), f"cause file {cause} does not exist"
    assert 1 <= case["cause_line"] <= len(cause.read_text(encoding="utf-8").splitlines())

    assert row["cause_in_evidence"] == case.get("evidence_sufficient", True), (
        "evidence_sufficient in the answer key disagrees with what the retrieval collects"
    )


def test_case_names_are_unique_across_both_keys():
    names = [Path(c["script"]).name for key in KEYS for c in json.loads((ROOT / key).read_text(encoding="utf-8"))]
    assert len(names) == len(set(names)) == 20


def test_baseline_prompt_has_the_traceback_and_the_whole_failing_file_only():
    case = next(c for c in json.loads((ROOT / KEYS[0]).read_text(encoding="utf-8")) if c["script"].endswith("run_bug10.py"))
    item = evaluate.prepare(case, baseline=True)
    assert "Traceback (most recent call last)" in item.prompt
    assert "1: from lookup import find_user" in item.prompt          # the whole failing file, numbered
    assert "def find_user" not in item.prompt                         # nothing a chatbot user would not paste
    assert item.row["evidence_sufficient"] is False


def test_baseline_counts_what_the_traceback_itself_prints():
    case = next(c for c in json.loads((ROOT / KEYS[0]).read_text(encoding="utf-8")) if c["script"].endswith("run_bug13.py"))
    item = evaluate.prepare(case, baseline=True)
    assert item.row["evidence_sufficient"] is True                    # Python echoes the bad line: run_bug13.py:3
    assert item.case["evidence_sufficient"] is True
