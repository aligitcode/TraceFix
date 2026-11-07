"""The whole of evaluate.py, run against a fake Gemini server (no key, no quota).

These are the situations that actually cost days: a 503 storm, a daily-limit stop that used to
throw away answers already saved, and a partial run that must not be saved as a result.
"""

import json
import time
from pathlib import Path

import pytest

import evaluate
from fake_gemini import GOOD_ANSWER, FakeGemini, overloaded, per_day, per_minute
from tracefix import investigator as inv

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[1]
GOOD = ("ok", GOOD_ANSWER)
FAST = ["--min-interval", "0", "--backoff-base", "1", "--pass-wait", "5"]


@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("GEMINI_MODEL", "fake-model")
    monkeypatch.setenv("TRACEFIX_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("TRACEFIX_RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setattr(inv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(evaluate, "load_dotenv", lambda *a, **k: None)
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)

    class Lab:
        results = tmp_path / "results"
        sleeps = slept

        @staticmethod
        def run(server, *args):
            monkeypatch.setenv("GEMINI_BASE_URL", server.url)
            return evaluate.main(list(args))

        @staticmethod
        def latest(name="latest.json"):
            return json.loads((tmp_path / "results" / name).read_text(encoding="utf-8"))

    return Lab


def test_every_bug_answered_and_scored(lab, capsys):
    with FakeGemini() as server:
        rc = lab.run(server, "--only", "1,2,3", *FAST)
    out = capsys.readouterr().out
    data = lab.latest()
    assert rc == 0 and server.requests == 3
    assert data["meta"]["complete"] is True and data["meta"]["requests_sent"] == 3
    assert all("llm_error" not in row and row["api_requests"] == 1 for row in data["rows"])
    assert data["rows"][0]["correct_behavior"] is True           # bug 1: the fake answer cites line 2
    assert "COMPLETE: every bug has an answer." in out


def test_503_storm_trips_the_breaker_instead_of_burning_the_quota_then_recovers(lab):
    # 3 failed requests in a row open the breaker. The old runner kept going and used the day's quota.
    with FakeGemini([overloaded(), overloaded(), overloaded()]) as server:
        rc = lab.run(server, "--only", "1,2,3", "--passes", "2", *FAST)
    data = lab.latest()
    assert rc == 0 and data["meta"]["complete"] is True
    assert server.requests == 6                                   # 3 failures + 3 answers, nothing wasted
    assert 5.0 in lab.sleeps                                      # it waited between passes
    assert data["rows"][0]["attempts"][0]["result"] == "503 UNAVAILABLE [transient]"


def test_a_storm_that_never_ends_stops_early_and_says_why(lab, capsys):
    with FakeGemini(default=overloaded()) as server:
        rc = lab.run(server, "--only", "1,2,3,4,5", "--passes", "2", *FAST)
    out = capsys.readouterr().out
    data = lab.latest()
    assert rc == 1 and data["meta"]["complete"] is False
    assert data["meta"]["stop_reason"] == "unavailable"
    assert server.requests <= 5                                   # 3 to trip the breaker + 1 probe + 1 more at most
    assert "Bugs without an answer" in out and "overloaded" in out


def test_per_minute_429_is_waited_out_and_does_not_stop_the_run(lab):
    # On Nov 2 a per-minute 429 contained the word "quota", and the old runner read it as the
    # daily limit and skipped every remaining bug.
    with FakeGemini([per_minute()]) as server:
        rc = lab.run(server, "--only", "1,2", *FAST)
    data = lab.latest()
    assert rc == 0 and data["meta"]["complete"] is True
    assert 9.0 in lab.sleeps                                      # retryDelay 7 s + 2 s margin


def test_daily_limit_stops_the_run_and_saved_answers_survive_for_next_time(lab, tmp_path, capsys):
    with FakeGemini([GOOD, GOOD, per_day()]) as first:
        rc1 = lab.run(first, "--only", "1,2,3,4", "--save-as", str(tmp_path / "kept.json"), *FAST)
    data1 = lab.latest()
    assert rc1 == 1 and first.requests == 3                       # 2 answers, the daily refusal, bug 4 never sent
    assert data1["meta"]["stop_reason"] == "daily_quota"
    assert [("llm_error" in row) for row in data1["rows"]] == [False, False, True, True]
    assert not (tmp_path / "kept.json").exists()                  # a partial run is never saved as a result
    assert "NOT saved" in capsys.readouterr().out

    # Next day: bugs 1 and 2 must come from the cache and cost nothing.
    with FakeGemini() as second:
        rc2 = lab.run(second, "--only", "1,2,3,4", "--save-as", str(tmp_path / "kept.json"), *FAST)
    data2 = lab.latest()
    assert rc2 == 0 and second.requests == 2
    assert data2["meta"]["answers_from_cache"] == 2 and data2["meta"]["complete"] is True
    assert json.loads((tmp_path / "kept.json").read_text(encoding="utf-8"))["meta"]["complete"] is True


def test_cached_answers_are_still_served_after_a_daily_stop_in_the_same_run(lab):
    # The bug fixed on Nov 2: once the quota was hit, bugs with saved answers were skipped too.
    with FakeGemini() as warm:
        lab.run(warm, "--only", "3,4", *FAST)                     # saves answers for bugs 3 and 4
    with FakeGemini([per_day()]) as server:
        rc = lab.run(server, "--only", "1,2,3,4", *FAST)          # bug 1 hits the daily limit
    rows = lab.latest()["rows"]
    assert rc == 1 and server.requests == 1
    assert [("llm_error" in row) for row in rows] == [True, True, False, False]


def test_cache_only_never_sends_a_request(lab, capsys):
    with FakeGemini() as warm:
        lab.run(warm, "--only", "1,2", *FAST)
    with FakeGemini() as server:
        rc = lab.run(server, "--only", "1,2,3", "--cache-only")
    rows = lab.latest()["rows"]
    assert rc == 1 and server.requests == 0
    assert [("llm_error" in row) for row in rows] == [False, False, True]
    assert "--cache-only" in rows[2]["llm_error"]


def test_baseline_sends_only_the_traceback_and_the_failing_file(lab):
    with FakeGemini() as server:
        lab.run(server, "--baseline", "--only", "10", *FAST)
        baseline_prompt = server.bodies[0]
    with FakeGemini() as server:
        lab.run(server, "--only", "10", *FAST)
        tracefix_prompt = server.bodies[0]
    assert "Traceback" in baseline_prompt and "def find_user" not in baseline_prompt
    assert "def find_user" in tracefix_prompt
    data = lab.latest("latest_baseline.json")
    row = data["rows"][0]
    assert data["meta"]["mode"] == "baseline"
    assert row["evidence_sufficient"] is False                    # lookup.py is not in what a chatbot is given
    assert row["false_confidence"] is True                        # the fake model said "high" anyway


def test_a_script_without_a_traceback_is_reported_not_asked(lab, tmp_path):
    quiet = tmp_path / "run_bug99.py"
    quiet.write_text("print('no error here')\n", encoding="utf-8")
    cases = tmp_path / "expected_quiet.json"
    cases.write_text(json.dumps([{
        "script": str(quiet), "error_type": "X", "file": "x.py", "line": 1,
        "cause_file": "x.py", "cause_line": 1, "evidence_sufficient": True}]), encoding="utf-8")
    with FakeGemini() as server:
        rc = lab.run(server, "--cases", str(cases), *FAST)
    data = lab.latest("latest_quiet.json")
    assert rc == 1 and server.requests == 0
    assert "no traceback" in data["rows"][0]["llm_error"]


def test_result_file_names_never_collide():
    class A:
        baseline = False
        cases = evaluate.DEFAULT_CASES

    a = A()
    assert evaluate.result_name(a, True) == "latest.json"
    assert evaluate.result_name(a, False) == "latest_no_llm.json"
    a.baseline = True
    assert evaluate.result_name(a, True) == "latest_baseline.json"
    a.cases = "examples/expected_heldout.json"
    assert evaluate.result_name(a, True) == "latest_baseline_heldout.json"


def test_unknown_bug_number_is_an_error_not_an_empty_success(lab, capsys):
    with FakeGemini() as server:
        rc = lab.run(server, "--only", "999")
    assert rc == 2 and server.requests == 0
