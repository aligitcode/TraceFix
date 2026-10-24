import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


def build_prompt(summary: dict, frame: dict, context: list[dict]) -> str:
    """Turn TraceFix evidence into a prompt for Gemini."""
    code = "\n".join(f"{item['line']}: {item['text']}" for item in context)
    return (
        "You are a careful software debugging assistant.\n"
        "Use ONLY the evidence below. If it is not enough, say so.\n\n"
        f"Error type: {summary['error_type']}\n"
        f"Error message: {summary['message']}\n"
        f"Failing file: {frame['file']}\n"
        f"Failing line: {frame['line']} in function {frame['function']}\n\n"
        "Code around the failure (line number: code):\n"
        f"{code}\n\n"
        "Reply as JSON with exactly these keys: "
        '"likely_cause" (string), '
        '"evidence_lines" (list of line numbers you relied on), '
        '"confidence" (one of "high", "medium", "low", "inconclusive"), '
        '"suggested_fix" (string).'
    )


def ask_gemini(prompt: str, attempts: int = 4) -> dict:
    """Send the prompt to Gemini, retrying on temporary errors (503, 429)."""
    load_dotenv()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    for attempt in range(1, attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except (errors.ServerError, errors.ClientError) as error:
            temporary = isinstance(error, errors.ServerError) or getattr(error, "code", None) == 429
            if not temporary or attempt == attempts:
                raise
            wait = 5 * attempt
            print(f"Gemini is busy (attempt {attempt}/{attempts}). Retrying in {wait}s...")
            time.sleep(wait)
