import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

CACHE_DIR = Path("results/cache")


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


def ask_gemini(prompt: str, attempts: int = 3) -> dict:
    """Ask Gemini. Reuses saved answers and stops early on daily quota errors."""
    load_dotenv()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    key = hashlib.sha256((model + prompt).encode("utf-8")).hexdigest()[:16]
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=20000, retry_options=types.HttpRetryOptions(attempts=1)))

    for attempt in range(1, attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            answer = json.loads(response.text)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(answer, indent=2), encoding="utf-8")
            return answer
        except (errors.ServerError, errors.ClientError) as error:
            text = str(error)
            if "PerDay" in text:
                raise RuntimeError(
                    "Daily free-tier quota used up for this model. "
                    "Try again tomorrow, or switch GEMINI_MODEL."
                ) from error
            temporary = isinstance(error, errors.ServerError) or getattr(error, "code", None) == 429
            if not temporary or attempt == attempts:
                raise
            wait = 10 * attempt
            print(f"Gemini is busy (attempt {attempt}/{attempts}). Retrying in {wait}s...")
            time.sleep(wait)

