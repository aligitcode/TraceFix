"""Work through the bugs that still need a Gemini answer, spending as few requests as possible."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from tracefix.resilience import (
    BudgetExhausted,
    CallFailed,
    DailyQuotaExceeded,
    FatalGeminiError,
    GeminiError,
    ServiceUnavailable,
)

NOT_ASKED = {
    "daily_quota": "not asked: the daily quota was already used up in this run",
    "budget": "not asked: the request limit (--max-requests) was reached",
    "fatal": "not asked: Gemini rejected the key or model, see the first error",
    "interrupted": "not asked: the run was interrupted",
    "unavailable": "not asked: Gemini stayed overloaded, so the run stopped to save quota",
}


@dataclass
class RunResult:
    answered: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)      # name -> why it has no answer
    unanswered: list = field(default_factory=list)
    stop_reason: str | None = None                  # daily_quota, budget, fatal, interrupted, unavailable
    passes_used: int = 0


def run_pending(items, ask_one, guard, passes=3, pass_wait=600.0, sleep=None, log=print) -> RunResult:
    """Call ask_one(item) for every item. ask_one must raise a GeminiError when it fails.

    A pass ends early when the circuit breaker opens (Gemini is clearly struggling).
    Items still unanswered go to the next pass, after a wait, and the first request of
    that pass is a single probe: if it fails the pass ends at once.
    """
    sleep = sleep or (lambda seconds: time.sleep(seconds))
    result = RunResult()
    pending = list(items)
    dropped = []  # failed in a way a retry cannot fix

    for pass_no in range(1, passes + 1):
        if not pending or result.stop_reason:
            break
        if pass_no > 1:
            log(f"Pass {pass_no} of {passes}: waiting {pass_wait:.0f}s, then probing with one request.")
            try:
                sleep(pass_wait)
            except KeyboardInterrupt:  # Ctrl+C while waiting must still save what we have
                result.stop_reason = "interrupted"
                break
            guard.breaker.half_open()
        result.passes_used = pass_no

        carried = []
        tripped = False
        for item in pending:
            if tripped or result.stop_reason:
                carried.append(item)
                continue
            try:
                ask_one(item)
                result.answered.append(item.name)
                result.errors.pop(item.name, None)
            except KeyboardInterrupt:
                result.stop_reason = "interrupted"
                carried.append(item)
            except DailyQuotaExceeded as error:
                result.stop_reason = "daily_quota"
                result.errors[item.name] = str(error)
                carried.append(item)
            except BudgetExhausted as error:
                result.stop_reason = "budget"
                result.errors[item.name] = str(error)
                carried.append(item)
            except FatalGeminiError as error:
                result.stop_reason = "fatal"
                result.errors[item.name] = str(error)
                carried.append(item)
            except ServiceUnavailable as error:
                tripped = True
                result.errors[item.name] = str(error)
                carried.append(item)
            except CallFailed as error:
                result.errors[item.name] = str(error)
                (carried if error.retryable else dropped).append(item)
            except GeminiError as error:
                result.errors[item.name] = str(error)
                carried.append(item)
        pending = carried

    if pending and not result.stop_reason:
        result.stop_reason = "unavailable"

    for item in pending + dropped:
        result.unanswered.append(item.name)
        result.errors.setdefault(item.name, NOT_ASKED.get(result.stop_reason, "not answered"))
    # keep the original order
    order = {item.name: i for i, item in enumerate(items)}
    result.unanswered.sort(key=order.get)
    return result
