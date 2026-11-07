from dataclasses import dataclass

from tracefix import resilience as r
from tracefix.runner import run_pending


@dataclass
class Bug:
    name: str


def make_guard(**kwargs):
    slept = []
    guard = r.CallGuard(sleep=slept.append, clock=lambda: 0.0, log=lambda message: None, **kwargs)
    return guard, slept


def run(script, names=("a", "b", "c"), **kwargs):
    """script: dict name -> list of outcomes (an exception to raise, or None for success), used in order."""
    calls = []
    script = {name: list(steps) for name, steps in script.items()}

    def ask_one(item):
        calls.append(item.name)
        steps = script.get(item.name, [])
        outcome = steps.pop(0) if steps else None
        if outcome is not None:
            raise outcome

    guard = kwargs.pop("guard", None) or make_guard()[0]
    result = run_pending([Bug(n) for n in names], ask_one, guard, log=lambda message: None,
                         sleep=kwargs.pop("sleep", lambda s: None), **kwargs)
    return result, calls


def test_everything_succeeds_in_one_pass():
    result, calls = run({})
    assert result.answered == ["a", "b", "c"]
    assert result.unanswered == [] and result.stop_reason is None
    assert result.passes_used == 1 and calls == ["a", "b", "c"]


def test_daily_quota_stops_the_run_and_later_bugs_are_not_asked():
    result, calls = run({"b": [r.DailyQuotaExceeded("daily")]})
    assert result.stop_reason == "daily_quota"
    assert result.answered == ["a"]
    assert result.unanswered == ["b", "c"]
    assert calls == ["a", "b"]                         # c was never sent
    assert "daily" in result.errors["b"]
    assert "daily quota" in result.errors["c"]         # explained, not just empty


def test_fatal_error_stops_the_run():
    result, calls = run({"a": [r.FatalGeminiError("bad key")]})
    assert result.stop_reason == "fatal" and calls == ["a"]
    assert result.unanswered == ["a", "b", "c"]


def test_budget_exhausted_stops_the_run():
    result, calls = run({"b": [r.BudgetExhausted("limit")]})
    assert result.stop_reason == "budget" and result.answered == ["a"]


def test_a_permanent_failure_drops_one_bug_but_the_run_continues():
    result, calls = run({"b": [r.CallFailed("bad request", retryable=False)]})
    assert result.answered == ["a", "c"]
    assert result.unanswered == ["b"]
    assert result.stop_reason is None
    assert calls == ["a", "b", "c"]                    # not retried in a later pass


def test_an_open_breaker_ends_the_pass_then_a_later_probe_recovers():
    guard, _ = make_guard()
    slept = []
    result, calls = run(
        {"a": [r.ServiceUnavailable("overloaded")]}, guard=guard, passes=2, pass_wait=600, sleep=slept.append
    )
    assert slept == [600]                              # waited before the second pass
    assert guard.breaker.probing                       # and probed carefully
    assert result.answered == ["a", "b", "c"]
    assert result.unanswered == [] and result.stop_reason is None
    assert calls == ["a", "a", "b", "c"]               # b and c were NOT sent while the breaker was open


def test_gemini_that_never_recovers_ends_as_unavailable_after_all_passes():
    always = [r.ServiceUnavailable("overloaded")] * 10
    result, calls = run({"a": always, "b": always, "c": always}, passes=3, pass_wait=1)
    assert result.stop_reason == "unavailable"
    assert result.passes_used == 3
    assert result.unanswered == ["a", "b", "c"]
    assert calls == ["a", "a", "a"]                    # one probe per pass, nothing else sent


def test_retryable_call_failures_are_carried_to_the_next_pass():
    result, calls = run({"b": [r.CallFailed("flaky", retryable=True)]}, passes=2, pass_wait=1)
    assert result.answered == ["a", "c", "b"]
    assert result.stop_reason is None and result.passes_used == 2


def test_ctrl_c_is_a_clean_stop():
    result, calls = run({"b": [KeyboardInterrupt()]})
    assert result.stop_reason == "interrupted"
    assert result.answered == ["a"] and result.unanswered == ["b", "c"]


def test_ctrl_c_during_the_wait_between_passes_is_also_a_clean_stop():
    def interrupted_sleep(seconds):
        raise KeyboardInterrupt

    always = [r.ServiceUnavailable("overloaded")] * 3
    result, calls = run({"a": always}, passes=3, pass_wait=600, sleep=interrupted_sleep)
    assert result.stop_reason == "interrupted"
    assert result.unanswered == ["a", "b", "c"]
    assert calls == ["a"]


def test_unanswered_keeps_the_original_order():
    result, _ = run({"a": [r.CallFailed("x", retryable=False)], "c": [r.CallFailed("y", retryable=False)]})
    assert result.unanswered == ["a", "c"]
