import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from tracefix.resilience import (
    DAILY,
    FATAL,
    PERMANENT,
    UNKNOWN,
    BadReply,
    CallFailed,
    CallGuard,
    DailyQuotaExceeded,
    FatalGeminiError,
    RetryPolicy,
    ServiceUnavailable,
    classify_error,
)

CACHE_DIR = Path("results/cache")
DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_TIMEOUT_S = 120
# LAST_CALL describes the most recent ask_gemini call:
# cached (answer came from disk), requests (HTTP requests sent), attempts (what each one returned), seconds.
LAST_CALL = {"cached": None, "requests": 0, "attempts": [], "seconds": 0.0}


def build_prompt(summary: dict, frame: dict, context: list[dict], definitions: list[dict] | None = None) -> str:
    """Turn TraceFix evidence into a prompt for Gemini."""
    code = "\n".join(f"{item['line']}: {item['text']}" for item in context)

    extra = ""
    citing = '"evidence_lines" (list of line numbers you relied on), '
    if definitions:
        blocks = []
        for d in definitions:
            name = Path(d["file"]).name
            blocks.append("\n".join(f"{name}:{l['line']}: {l['text']}" for l in d["lines"]))
        extra = (
            "Additional code evidence: functions called near the failure, other traceback frames, imported constants (file:line: code):\n"
            + "\n".join(blocks)
            + "\n\n"
        )
        citing = (
            '"evidence_lines" (list; use plain numbers for lines of the failing file '
            'and "file.py:line" strings for lines of the additional evidence above), '
        )

    return (
        "You are a careful software debugging assistant.\n"
        "Use ONLY the evidence below. If it is not enough, say so.\n\n"
        f"Error type: {summary['error_type']}\n"
        f"Error message: {summary['message']}\n"
        f"Failing file: {frame['file']}\n"
        f"Failing line: {frame['line']} in function {frame['function']}\n\n"
        "Code around the failure (line number: code):\n"
        f"{code}\n\n"
        f"{extra}"
        "Reply as JSON with exactly these keys: "
        '"likely_cause" (string), '
        f"{citing}"
        '"confidence" (one of "high", "medium", "low", "inconclusive"), '
        '"suggested_fix" (string).'
    )


def model_name() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def _cache_dir() -> Path:
    env = os.environ.get("TRACEFIX_CACHE_DIR")
    return Path(env) if env else CACHE_DIR


def _cache_file(model: str, prompt: str) -> Path:
    # This key must not change: it is what makes answers saved earlier still count.
    key = hashlib.sha256((model + prompt).encode("utf-8")).hexdigest()[:16]
    return _cache_dir() / f"{key}.json"


def _read_cache(model: str, prompt: str):
    path = _cache_file(model, prompt)
    if not path.exists():
        return None
    try:
        answer = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return answer if isinstance(answer, dict) else None


def get_cached(prompt: str):
    """The saved answer for this prompt (and the current model), or None. Costs no request."""
    load_dotenv()
    return _read_cache(model_name(), prompt)


def _make_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise FatalGeminiError("GEMINI_API_KEY is not set. Put it in the .env file (never paste it into chat).")
    seconds = float(os.environ.get("GEMINI_TIMEOUT_S", DEFAULT_TIMEOUT_S))
    options = {
        "timeout": int(seconds * 1000),  # the SDK takes milliseconds
        "retry_options": types.HttpRetryOptions(attempts=1),  # we do our own, counted retries
    }
    base_url = os.environ.get("GEMINI_BASE_URL")  # only used by the tests (a fake local server)
    if base_url:
        options["base_url"] = base_url
    return genai.Client(api_key=key, http_options=types.HttpOptions(**options))


def _parse_reply(response) -> dict:
    text = getattr(response, "text", None)
    if not text:
        reason = None
        try:
            reason = response.candidates[0].finish_reason
        except Exception:
            pass
        raise BadReply(f"Gemini returned no text (finish reason: {reason})")
    try:
        answer = json.loads(text)
    except ValueError as error:
        raise BadReply(f"Gemini's reply was not valid JSON: {error}") from error
    if not isinstance(answer, dict):
        raise BadReply("Gemini's reply was JSON but not an object")
    return answer


def ask_gemini(prompt: str, attempts: int = 3, guard: CallGuard | None = None) -> dict:
    """Ask Gemini. Saved answers are reused, so the same prompt is never paid for twice.

    Without a guard (investigate.py) `attempts` tries are made with backoff. With a guard,
    guard.policy.attempts decides, and the guard also paces and counts the requests.
    Raises a GeminiError subclass when no answer could be obtained.
    """
    load_dotenv()
    model = model_name()
    LAST_CALL.update(cached=False, requests=0, attempts=[], seconds=0.0)

    cached = _read_cache(model, prompt)
    if cached is not None:
        LAST_CALL["cached"] = True
        return cached

    guard = guard or CallGuard(RetryPolicy(attempts=attempts))
    client = _make_client()
    started = time.monotonic()
    try:
        return _ask_with_retries(client, model, prompt, guard)
    finally:
        LAST_CALL["seconds"] = round(time.monotonic() - started, 1)


def _ask_with_retries(client, model, prompt, guard: CallGuard) -> dict:
    policy = guard.policy
    for attempt in range(1, policy.attempts + 1):
        guard.before_request()
        LAST_CALL["requests"] += 1
        began = time.monotonic()
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            answer = _parse_reply(response)
        except Exception as error:
            info = classify_error(error)
            if info.kind == UNKNOWN:
                raise  # a bug in our own code: show it, do not hide it as a Gemini problem
            LAST_CALL["attempts"].append(
                {"result": info.short(), "seconds": round(time.monotonic() - began, 1)}
            )
            guard.after_failure(info)
            detail = f"{info.short()}: {info.message[:150]}"
            if info.kind == DAILY:
                raise DailyQuotaExceeded(
                    "Daily free-tier quota used up for this model. "
                    f"It resets at midnight Pacific time (about 10:00 in Cairo). ({info.short()})",
                    info,
                ) from error
            if info.kind == FATAL:
                raise FatalGeminiError(f"Gemini rejected the request: {detail}", info) from error
            if info.kind == PERMANENT:
                raise CallFailed(f"Gemini refused this request: {detail}", info, retryable=False) from error
            if guard.breaker.is_open:
                raise ServiceUnavailable(
                    f"{guard.breaker.failures} failed request(s) in a row; stopping to save quota. "
                    f"Last error: {detail}",
                    info,
                ) from error
            if attempt == policy.attempts:
                raise CallFailed(
                    f"Gemini failed after {attempt} attempt(s): {detail}", info, retryable=True
                ) from error
            guard.pause(policy.wait_for(info, attempt, guard.rng), f"{info.short()}, then retry")
        else:
            LAST_CALL["attempts"].append({"result": "ok", "seconds": round(time.monotonic() - began, 1)})
            guard.after_success()
            path = _cache_file(model, prompt)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(answer, indent=2), encoding="utf-8")
            return answer
    raise CallFailed("Gemini was not asked: attempts is 0", retryable=False)  # pragma: no cover
