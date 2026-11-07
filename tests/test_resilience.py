import httpx
import pytest
from google.genai import errors

from tracefix import resilience as r


def api_error(code, status, message="x", details=None):
    body = {"error": {"code": code, "message": message, "status": status}}
    if details:
        body["error"].update(details)
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, body)


PER_DAY = {
    "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "44520s"},
    ]
}
PER_MINUTE = {
    "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "12s"},
    ]
}


# ---- classification: the bug that threw away a whole run was a per-minute 429 read as "daily" ----

def test_daily_quota_is_recognised_from_the_quota_id():
    info = r.classify_error(api_error(429, "RESOURCE_EXHAUSTED", details=PER_DAY))
    assert info.kind == r.DAILY
    assert info.retry_after == 44520.0


def test_per_minute_429_is_not_daily_even_though_it_says_quota():
    message = "You exceeded your current quota, please check your plan and billing details."
    info = r.classify_error(api_error(429, "RESOURCE_EXHAUSTED", message, PER_MINUTE))
    assert info.kind == r.RATE
    assert info.retry_after == 12.0


def test_429_with_only_a_message_hint():
    info = r.classify_error(api_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded. Please retry in 7.5s."))
    assert (info.kind, info.retry_after) == (r.RATE, 7.5)


def test_429_with_no_hint_is_a_rate_limit_without_a_wait():
    info = r.classify_error(api_error(429, "RESOURCE_EXHAUSTED"))
    assert (info.kind, info.retry_after) == (r.RATE, None)


def test_daily_quota_recognised_from_text_alone():
    info = r.classify_error(api_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded for metric ... PerDay ..."))
    assert info.kind == r.DAILY


def test_a_very_long_retry_delay_means_a_quota_window_not_a_minute_limit():
    details = {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3600s"}]}
    assert r.classify_error(api_error(429, "RESOURCE_EXHAUSTED", details=details)).kind == r.DAILY


@pytest.mark.parametrize("code,status", [(500, "INTERNAL"), (503, "UNAVAILABLE"), (504, "DEADLINE_EXCEEDED"), (408, "TIMEOUT")])
def test_server_side_trouble_is_transient(code, status):
    assert r.classify_error(api_error(code, status)).kind == r.TRANSIENT


@pytest.mark.parametrize("code", [401, 403, 404])
def test_auth_and_unknown_model_are_fatal(code):
    assert r.classify_error(api_error(code, "X")).kind == r.FATAL


def test_invalid_key_reported_as_400_is_fatal():
    info = r.classify_error(api_error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."))
    assert info.kind == r.FATAL


def test_other_400_is_permanent_and_not_retried():
    assert r.classify_error(api_error(400, "INVALID_ARGUMENT", "bad request")).kind == r.PERMANENT


def test_network_problems_are_transient():
    assert r.classify_error(httpx.ReadTimeout("slow")).kind == r.TRANSIENT
    assert r.classify_error(ConnectionResetError("reset")).kind == r.TRANSIENT


def test_bad_reply_is_retryable_and_our_own_bugs_are_unknown():
    assert r.classify_error(r.BadReply("not json")).kind == r.BAD_REPLY
    assert r.classify_error(KeyError("oops")).kind == r.UNKNOWN


@pytest.mark.parametrize(
    "value,expected",
    [(12, 12.0), ("12s", 12.0), ("12.5s", 12.5), ("1h2m3s", 3723.0), ({"seconds": 3, "nanos": 5e8}, 3.5), ("soon", None), (True, None)],
)
def test_duration_parsing(value, expected):
    assert r._duration(value) == expected


# ---- waiting ----

def test_rate_limit_waits_as_long_as_google_asks_plus_a_margin():
    policy = r.RetryPolicy(rate_margin=2.0)
    info = r.ErrorInfo(r.RATE, "429", 429, retry_after=12.0)
    assert policy.wait_for(info, 1) == 14.0


def test_rate_limit_without_hint_uses_the_default_and_the_cap():
    policy = r.RetryPolicy(rate_default=30.0, rate_margin=2.0, rate_cap=20.0)
    assert policy.wait_for(r.ErrorInfo(r.RATE, "429", 429), 1) == 20.0


def test_transient_backoff_doubles_and_is_capped():
    policy = r.RetryPolicy(backoff_base=20.0, backoff_cap=60.0, jitter=0.25)
    info = r.ErrorInfo(r.TRANSIENT, "503", 503)
    middle = lambda: 0.5  # jitter factor exactly 1
    assert [policy.wait_for(info, n, middle) for n in (1, 2, 3, 4)] == [20.0, 40.0, 60.0, 60.0]
    assert policy.wait_for(info, 1, lambda: 0.0) == 15.0   # -25%
    assert policy.wait_for(info, 1, lambda: 1.0) == 25.0   # +25%


# ---- circuit breaker ----

def test_breaker_opens_after_threshold_and_success_resets():
    breaker = r.CircuitBreaker(3)
    breaker.record_failure(); breaker.record_failure()
    assert not breaker.is_open
    breaker.record_failure()
    assert breaker.is_open
    breaker.record_success()
    assert not breaker.is_open


def test_after_half_open_a_single_failure_reopens_it():
    breaker = r.CircuitBreaker(3)
    for _ in range(3):
        breaker.record_failure()
    breaker.half_open()
    assert not breaker.is_open        # one probe is allowed
    breaker.record_failure()
    assert breaker.is_open            # ...and if it fails the breaker closes the door again


# ---- guard ----

def make_guard(**kwargs):
    clock = {"now": 100.0}
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        clock["now"] += seconds

    guard = r.CallGuard(sleep=sleep, clock=lambda: clock["now"], log=lambda message: None, **kwargs)
    return guard, slept, clock


def test_guard_enforces_the_request_budget():
    guard, _, _ = make_guard(max_requests=2)
    guard.before_request(); guard.before_request()
    with pytest.raises(r.BudgetExhausted):
        guard.before_request()
    assert guard.requests == 2


def test_guard_zero_budget_means_no_limit():
    guard, _, _ = make_guard(max_requests=0)
    for _ in range(50):
        guard.before_request()
    assert guard.requests == 50


def test_guard_spaces_requests_by_min_interval():
    guard, slept, clock = make_guard(min_interval=13.0)
    guard.before_request()                  # first request: no wait
    clock["now"] += 5.0                     # 5 s pass
    guard.before_request()                  # needs 8 more seconds
    assert slept == [8.0]
    clock["now"] += 20.0
    guard.before_request()                  # already 20 s since the last one: no wait
    assert slept == [8.0]


def test_guard_stops_sending_when_the_breaker_is_open():
    guard, _, _ = make_guard(breaker_threshold=2)
    info = r.ErrorInfo(r.TRANSIENT, "503", 503)
    guard.before_request(); guard.after_failure(info)
    guard.before_request(); guard.after_failure(info)
    with pytest.raises(r.ServiceUnavailable):
        guard.before_request()
    assert guard.requests == 2


def test_permanent_errors_do_not_trip_the_breaker():
    guard, _, _ = make_guard(breaker_threshold=1)
    guard.after_failure(r.ErrorInfo(r.PERMANENT, "400", 400))
    assert not guard.breaker.is_open
