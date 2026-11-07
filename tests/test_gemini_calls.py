"""ask_gemini against a fake local Gemini server, through the real google-genai SDK.

No key and no quota are used: GEMINI_BASE_URL points the SDK at a fake server that returns
the same error codes and bodies the real API does.
"""

import json

import pytest

from fake_gemini import GOOD_ANSWER, FakeGemini, deadline, error, overloaded, per_day, per_minute
from tracefix import investigator as inv
from tracefix import resilience as r


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("GEMINI_MODEL", "fake-model")
    monkeypatch.setenv("TRACEFIX_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.delenv("GEMINI_TIMEOUT_S", raising=False)
    monkeypatch.setattr(inv, "load_dotenv", lambda *a, **k: None)  # never read a real .env in tests
    return tmp_path


def guard(**kwargs):
    slept = []
    policy = kwargs.pop("policy", r.RetryPolicy(attempts=3, jitter=0.0))
    g = r.CallGuard(policy=policy, sleep=slept.append, clock=lambda: 0.0, log=lambda m: None, **kwargs)
    return g, slept


def ask(server, monkeypatch, prompt="p1", **kwargs):
    monkeypatch.setenv("GEMINI_BASE_URL", server.url)
    return inv.ask_gemini(prompt, **kwargs)


def test_good_answer_is_returned_and_saved(env, monkeypatch):
    with FakeGemini() as server:
        g, _ = guard()
        assert ask(server, monkeypatch, guard=g) == GOOD_ANSWER
    assert server.requests == 1 and g.requests == 1
    assert inv.LAST_CALL["cached"] is False and inv.LAST_CALL["attempts"][0]["result"] == "ok"
    assert len(list((env / "cache").glob("*.json"))) == 1


def test_second_ask_comes_from_the_cache_and_sends_nothing(env, monkeypatch):
    with FakeGemini() as server:
        ask(server, monkeypatch, guard=guard()[0])
        before = server.requests
        assert ask(server, monkeypatch, guard=guard()[0]) == GOOD_ANSWER
        assert server.requests == before
    assert inv.LAST_CALL["cached"] is True and inv.LAST_CALL["requests"] == 0


def test_cache_key_is_unchanged_so_old_answers_still_count(env, monkeypatch):
    # sha256("fake-model" + "p1")[:16]; if this changes, every saved answer is silently lost.
    import hashlib
    expected = hashlib.sha256(b"fake-modelp1").hexdigest()[:16] + ".json"
    with FakeGemini() as server:
        ask(server, monkeypatch, guard=guard()[0])
    assert (env / "cache" / expected).exists()


def test_503_is_retried_after_a_backoff_and_then_succeeds(env, monkeypatch):
    with FakeGemini([overloaded()]) as server:
        g, slept = guard()
        assert ask(server, monkeypatch, guard=g) == GOOD_ANSWER
    assert server.requests == 2 and g.requests == 2
    assert slept == [20.0]                                   # first backoff step, no jitter
    results = [a["result"] for a in inv.LAST_CALL["attempts"]]
    assert results == ["503 UNAVAILABLE [transient]", "ok"]


def test_504_is_handled_like_503(env, monkeypatch):
    with FakeGemini([deadline()]) as server:
        assert ask(server, monkeypatch, guard=guard()[0]) == GOOD_ANSWER
    assert server.requests == 2


def test_per_minute_429_waits_as_long_as_google_asks_and_retries(env, monkeypatch):
    with FakeGemini([per_minute()]) as server:
        g, slept = guard()
        assert ask(server, monkeypatch, guard=g) == GOOD_ANSWER
    assert slept == [9.0]                                    # 7 s from retryDelay + 2 s margin
    assert server.requests == 2


def test_daily_429_stops_at_once_without_retrying(env, monkeypatch):
    with FakeGemini([per_day()]) as server:
        g, slept = guard()
        with pytest.raises(r.DailyQuotaExceeded) as caught:
            ask(server, monkeypatch, guard=g)
    assert server.requests == 1 and slept == []
    assert "midnight Pacific" in str(caught.value)


def test_failed_answers_are_never_cached(env, monkeypatch):
    with FakeGemini([per_day()]) as server:
        with pytest.raises(r.DailyQuotaExceeded):
            ask(server, monkeypatch, guard=guard()[0])
    assert not (env / "cache").exists() or not list((env / "cache").glob("*.json"))


@pytest.mark.parametrize("code", [401, 403, 404])
def test_bad_key_or_model_is_fatal_and_not_retried(env, monkeypatch, code):
    with FakeGemini([error(code, "PERMISSION_DENIED", message="nope")]) as server:
        with pytest.raises(r.FatalGeminiError):
            ask(server, monkeypatch, guard=guard()[0])
    assert server.requests == 1


def test_a_plain_400_is_permanent_and_not_retried(env, monkeypatch):
    with FakeGemini([error(400, "INVALID_ARGUMENT", message="prompt too long")]) as server:
        with pytest.raises(r.CallFailed) as caught:
            ask(server, monkeypatch, guard=guard()[0])
    assert caught.value.retryable is False and server.requests == 1


def test_reply_that_is_not_json_is_retried(env, monkeypatch):
    with FakeGemini([("text", "Sorry, I cannot help with that.")]) as server:
        assert ask(server, monkeypatch, guard=guard()[0]) == GOOD_ANSWER
    assert server.requests == 2


def test_empty_reply_is_retried(env, monkeypatch):
    with FakeGemini([("empty",)]) as server:
        assert ask(server, monkeypatch, guard=guard()[0]) == GOOD_ANSWER
    assert server.requests == 2


def test_json_that_is_not_an_object_is_a_bad_reply(env, monkeypatch):
    with FakeGemini([("text", json.dumps([1, 2, 3]))]) as server:
        assert ask(server, monkeypatch, guard=guard()[0]) == GOOD_ANSWER
    assert server.requests == 2


def test_three_failures_in_a_row_open_the_breaker_and_stop_sending(env, monkeypatch):
    # Without the breaker this would keep going for 6 attempts and could burn the daily quota.
    with FakeGemini(default=overloaded()) as server:
        g, _ = guard(policy=r.RetryPolicy(attempts=6, jitter=0.0), breaker_threshold=3)
        with pytest.raises(r.ServiceUnavailable):
            ask(server, monkeypatch, guard=g)
    assert server.requests == 3 and g.requests == 3


def test_attempts_run_out_gives_a_retryable_failure(env, monkeypatch):
    with FakeGemini(default=overloaded()) as server:
        g, slept = guard(policy=r.RetryPolicy(attempts=2, jitter=0.0), breaker_threshold=10)
        with pytest.raises(r.CallFailed) as caught:
            ask(server, monkeypatch, guard=g)
    assert caught.value.retryable is True and server.requests == 2 and slept == [20.0]


def test_the_request_budget_is_a_hard_cap(env, monkeypatch):
    with FakeGemini(default=overloaded()) as server:
        g, _ = guard(policy=r.RetryPolicy(attempts=5, jitter=0.0), max_requests=2, breaker_threshold=10)
        with pytest.raises(r.BudgetExhausted):
            ask(server, monkeypatch, guard=g)
    assert server.requests == 2


def test_client_timeout_is_a_transient_failure_not_a_crash(env, monkeypatch):
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "0.3")
    with FakeGemini([("delay", 2.0)]) as server:
        g, _ = guard(policy=r.RetryPolicy(attempts=1, jitter=0.0))
        with pytest.raises(r.CallFailed) as caught:
            ask(server, monkeypatch, guard=g)
    assert caught.value.retryable is True
    assert "transient" in str(caught.value)


def test_missing_key_is_fatal_and_sends_nothing(env, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with FakeGemini() as server:
        with pytest.raises(r.FatalGeminiError):
            ask(server, monkeypatch, guard=guard()[0])
    assert server.requests == 0


def test_timeout_default_is_120_seconds_and_overridable(env, monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "http://127.0.0.1:9")
    assert inv._make_client()._api_client._http_options.timeout == 120000
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "45")
    assert inv._make_client()._api_client._http_options.timeout == 45000


def test_build_prompt_is_byte_for_byte_what_it_was(env):
    """The cache key is sha256(model + prompt). Reword the prompt and every saved answer is lost."""
    import hashlib

    summary = {"error_type": "TypeError", "message": "boom"}
    frame = {"file": "a.py", "line": "2", "function": "f"}
    context = [{"line": 1, "text": "x = 1"}, {"line": 2, "text": "y = x + None"}]
    definitions = [{"file": "b.py", "lines": [{"line": 3, "text": "return None"}]}]
    # Both hashes were computed from the original build_prompt (git commit 881897f).
    with_definitions = inv.build_prompt(summary, frame, context, definitions)
    without_definitions = inv.build_prompt(summary, frame, context)
    assert hashlib.sha256(with_definitions.encode()).hexdigest()[:16] == "a0eff2f46a5cd322"
    assert hashlib.sha256(without_definitions.encode()).hexdigest()[:16] == "774aa05c487dbd53"
