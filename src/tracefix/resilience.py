"""Safe handling of Gemini failures.

The free tier allows about 20 requests per day per model, and a request that
fails with 503 or 504 still seems to use one of them (see
docs/gemini_quota_notes.md). So retrying quickly, or retrying while Google is
overloaded, burns the day's allowance for nothing. This module decides, for
every error, whether to wait and retry, give up on one bug, or stop the whole
run, and it keeps a hard cap on how many requests one run may send.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

DAILY = "daily_quota"    # per-day limit used up: stop the whole run
RATE = "rate_limit"      # per-minute limit: wait as long as Google asks, then retry
TRANSIENT = "transient"  # 500/503/504, timeouts, dropped connections: back off, retry
BAD_REPLY = "bad_reply"  # Gemini answered, but not with usable JSON: retry
PERMANENT = "permanent"  # this one request can never work (other 4xx): do not retry
FATAL = "fatal"          # bad key, no permission, unknown model: stop the whole run
UNKNOWN = "unknown"      # not a Gemini or network error: a bug in our own code

RETRYABLE = (RATE, TRANSIENT, BAD_REPLY)

# A 429 that asks for a wait this long is a quota window, not a per-minute limit.
LONG_WAIT_SECONDS = 900.0
NETWORK_MODULES = {"httpx", "httpx2", "httpcore", "aiohttp", "requests", "urllib3", "ssl", "socket"}
FATAL_TEXT = ("api key not valid", "api_key_invalid", "location is not supported", "failed_precondition")


class BadReply(ValueError):
    """Gemini answered, but the answer was empty or not a JSON object."""


class GeminiError(RuntimeError):
    """Base class for every failure the runner knows how to handle."""

    def __init__(self, message, info=None, retryable=False):
        super().__init__(message)
        self.info = info
        self.retryable = retryable


class DailyQuotaExceeded(GeminiError):
    """The per-day limit is used up. Nothing more can be asked until it resets."""


class FatalGeminiError(GeminiError):
    """Bad key, no permission, unknown model, missing key: retrying cannot help."""


class BudgetExhausted(GeminiError):
    """The request limit chosen for this run has been reached."""


class ServiceUnavailable(GeminiError):
    """Too many failed requests in a row. Stop sending, wait, probe again later."""

    def __init__(self, message, info=None):
        super().__init__(message, info, retryable=True)


class CallFailed(GeminiError):
    """One bug could not be answered (retryable=True when a later pass may work)."""


@dataclass(frozen=True)
class ErrorInfo:
    kind: str
    label: str
    code: int | None = None
    retry_after: float | None = None
    quota_ids: tuple = ()
    message: str = ""

    def short(self) -> str:
        return f"{self.label} [{self.kind}]"


def _find_values(node, key):
    """Yield every value stored under `key` anywhere inside nested dicts and lists."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                yield value
            yield from _find_values(value, key)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _find_values(value, key)


_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0}
_RETRY_IN = re.compile(r"retry in\s+((?:\d+(?:\.\d+)?[hms](?![a-z])\s*)+)", re.IGNORECASE)
_PART = re.compile(r"(\d+(?:\.\d+)?)([hms])", re.IGNORECASE)


def _duration(value):
    """Seconds from 12, '12s', '12.5s', '1h2m3s' or {'seconds': 12, 'nanos': 5e8}."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        try:
            return float(value.get("seconds", 0)) + float(value.get("nanos", 0)) / 1e9
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = _PART.findall(value)
        if parts and "".join(n + u for n, u in parts) == value.replace(" ", ""):
            return sum(float(n) * _UNIT_SECONDS[u.lower()] for n, u in parts)
    return None


def _retry_after(details, text):
    for value in _find_values(details, "retryDelay"):
        seconds = _duration(value)
        if seconds is not None:
            return seconds
    found = _RETRY_IN.search(text)  # "Please retry in 12.3s." or "retry in 12h22m10s"
    return _duration(found.group(1).replace(" ", "")) if found else None


def classify_error(error: BaseException) -> ErrorInfo:
    """Turn any exception from a Gemini call into an ErrorInfo with a kind."""
    code = getattr(error, "code", None)
    code = code if isinstance(code, int) and not isinstance(code, bool) else None
    status = getattr(error, "status", None)
    details = getattr(error, "details", None)
    text = str(error)
    lowered = text.lower()
    quota_ids = tuple(str(v) for v in _find_values(details, "quotaId"))
    retry_after = _retry_after(details, text)
    message = str(getattr(error, "message", None) or text)
    label = f"{code} {status}".strip() if code is not None else type(error).__name__

    def make(kind):
        return ErrorInfo(kind, label, code, retry_after, quota_ids, message)

    if isinstance(error, BadReply):
        return make(BAD_REPLY)

    if code is not None:
        if code == 429:
            daily = (
                any("perday" in q.lower() for q in quota_ids)
                or "perday" in lowered
                or "per day" in lowered
                or (retry_after is not None and retry_after >= LONG_WAIT_SECONDS)
            )
            return make(DAILY if daily else RATE)
        if code in (401, 403, 404) or any(t in lowered for t in FATAL_TEXT):
            return make(FATAL)
        if code == 408 or code >= 500:
            return make(TRANSIENT)
        return make(PERMANENT)

    root = type(error).__module__.split(".")[0]
    if isinstance(error, OSError) or root in NETWORK_MODULES:
        return make(TRANSIENT)
    return make(UNKNOWN)


@dataclass
class RetryPolicy:
    attempts: int = 2          # tries per bug per pass; every try may cost one request
    backoff_base: float = 20.0
    backoff_cap: float = 120.0
    jitter: float = 0.25
    rate_margin: float = 2.0   # extra seconds on top of the wait Google asks for
    rate_default: float = 30.0  # wait for a per-minute 429 that gives no hint
    rate_cap: float = 900.0

    def wait_for(self, info: ErrorInfo, attempt: int, rng=random.random) -> float:
        if info.kind == RATE:
            hint = info.retry_after if info.retry_after is not None else self.rate_default
            return min(self.rate_cap, hint + self.rate_margin)
        delay = min(self.backoff_cap, self.backoff_base * (2 ** (attempt - 1)))
        return delay * (1 + self.jitter * (2 * rng() - 1))


class CircuitBreaker:
    """Opens after `threshold` failures in a row; after half_open() one failure reopens it."""

    def __init__(self, threshold: int = 3):
        self.threshold = max(1, threshold)
        self.failures = 0
        self.probing = False

    @property
    def is_open(self) -> bool:
        return self.failures >= (1 if self.probing else self.threshold)

    def record_success(self):
        self.failures = 0
        self.probing = False

    def record_failure(self):
        self.failures += 1

    def half_open(self):
        self.failures = 0
        self.probing = True


class CallGuard:
    """Decides whether a request may be sent now, and counts every request sent."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        max_requests: int | None = None,
        breaker_threshold: int = 3,
        min_interval: float = 0.0,
        sleep=None,
        clock=None,
        log=None,
        rng=random.random,
    ):
        self.policy = policy or RetryPolicy()
        self.max_requests = max_requests or None  # None or 0 means no limit
        self.breaker = CircuitBreaker(breaker_threshold)
        self.min_interval = min_interval
        # Looked up at call time (not bound at import) so tests can replace time.sleep.
        self.sleep = sleep or (lambda seconds: time.sleep(seconds))
        self.clock = clock or (lambda: time.monotonic())
        self.log = log or (lambda message: print(message, flush=True))
        self.rng = rng
        self.requests = 0
        self._last_sent = None

    def before_request(self):
        if self.breaker.is_open:
            raise ServiceUnavailable(
                f"{self.breaker.failures} failed request(s) in a row, so no more were sent "
                "(this protects the daily quota)."
            )
        if self.max_requests is not None and self.requests >= self.max_requests:
            raise BudgetExhausted(f"Request limit reached ({self.max_requests}); no more were sent.")
        if self._last_sent is not None and self.min_interval > 0:
            wait = self.min_interval - (self.clock() - self._last_sent)
            if wait > 0:
                self.sleep(wait)
        self.requests += 1
        self._last_sent = self.clock()

    def after_success(self):
        self.breaker.record_success()

    def after_failure(self, info: ErrorInfo):
        if info.kind in RETRYABLE:
            self.breaker.record_failure()

    def pause(self, seconds: float, why: str):
        self.log(f"  waiting {seconds:.0f}s ({why})")
        self.sleep(seconds)
