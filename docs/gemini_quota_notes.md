# Gemini free-tier quota: what we measured and what we only suspect

These notes explain why `evaluate.py` is built the way it is. Everything marked *measured*
comes from runs on the author's machine; everything marked *inference* is a conclusion drawn
from those runs, not a fact confirmed by Google.

## What Google documents

- Limits are applied **per project, not per API key**, and are set **separately for each model**.
  Hitting any one of requests per minute (RPM), tokens per minute (TPM) or requests per day (RPD)
  triggers a `429 RESOURCE_EXHAUSTED`.
- Daily quotas reset at **midnight Pacific time**, which is about 10:00 in Cairo.
- The rate-limits page does **not** say whether a request that fails (503, 504, 429) still counts
  toward the daily limit. Source: <https://aistudio.google.com/docs/rate-limits.md>
  (fetched 2026-11-07; the page does not list numeric free-tier values).

## What we measured (free tier, `gemini-3.8-flash`, about 20 requests per day)

| Day | Requests that reached Google before the daily refusal | Answers received |
|---|---|---|
| Thu 29 Oct | 1 test call + 14 + 5 = 20 | 2 |
| Sun 1 Nov | 12 + 8 = 20 | 4 |

The 503 and 504 replies on those days used up the same 20 requests as the answers did.

**Inference:** a request that fails with 503/504 still costs one of the 20. Two separate days
add up to exactly 20, which fits this and is unlikely to be chance, but it is not proof.
The practical consequence is the same either way: retrying blindly while Google is overloaded
wastes the day, so the runner stops early (circuit breaker) instead of retrying.

## The Nov 2 error that cost a whole run

On Nov 2 a run saw six `503 UNAVAILABLE` and then `429 RESOURCE_EXHAUSTED` ("You exceeded your
current quota"). The old code stopped the whole run on any error containing the word "quota".

**Inference:** this 429 was not the daily limit. The daily limit is recognised by the text
`PerDay` (the code did that check first and would have raised the "daily quota used up" message,
as it did on Nov 1), and that check did not fire. The likeliest explanation is a per-minute
limit: six requests were sent about four seconds apart. The raw text was cut to 200 characters
in the saved file, so this cannot be confirmed; the new runner keeps the full error text.

## How the runner responds

| Situation | What it does |
|---|---|
| Answer already saved | Uses it. Costs nothing, always, even after a daily stop. |
| Daily limit (`PerDay` in the quota id or text, or a retry delay of 15 minutes or more) | Stops the run. Nothing else can work until the reset. |
| Per-minute 429 | Waits as long as Google asks (plus 2 s) and retries. |
| 500 / 503 / 504, timeouts, dropped connections | Backs off (20 s, 40 s, ...) and retries. |
| 3 failed requests in a row | Stops the pass (circuit breaker), waits 10 minutes, probes with **one** request. |
| Bad key, unknown model, missing key | Stops the run at once. |
| Other 4xx for one request | Gives up on that bug, continues with the rest. |
| More than `--max-requests` (default 20) | Stops. |
| Requests | At least 13 s apart (stays under 5 requests per minute). |
| Ctrl+C | Saves what it has. |

Request timeout is 120 s (it was 20 s, which made every real prompt fail with 504 on Oct 29).
Override with `GEMINI_TIMEOUT_S`.

## What was never tested

All of the above is tested against a **fake local server** that returns the same status codes and
bodies. It has not been run against the real Google API from this workspace (no key here), so the
first real run is the real test. If something unexpected happens, `results/latest.json` keeps the
full text of every error.
