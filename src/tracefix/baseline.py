"""The plain-chatbot baseline.

A developer who pastes a crash into a chatbot gives it the traceback and, at best, the
file where the error was raised. This module builds exactly that and nothing more, so
TraceFix's extra evidence (called functions, other frames, imported constants) can be
compared against it with the same model, the same JSON format and the same scoring.
"""

from pathlib import Path


def build_baseline_prompt(error_text: str, failing: dict, source: list[dict]) -> str:
    """Traceback plus the whole failing file, in the same JSON reply format as TraceFix."""
    code = "\n".join(f"{item['line']}: {item['text']}" for item in source)
    return (
        "You are a careful software debugging assistant.\n"
        "Use ONLY the information below. If it is not enough, say so.\n\n"
        "A Python program crashed with this traceback:\n"
        f"{error_text.strip()}\n\n"
        f"Source of {Path(failing['file']).name}, the file where the error was raised (line number: code):\n"
        f"{code}\n\n"
        "Reply as JSON with exactly these keys: "
        '"likely_cause" (string), '
        '"evidence_lines" (list; use plain numbers for lines of the source file above '
        'and "file.py:line" strings for lines that only appear in the traceback), '
        '"confidence" (one of "high", "medium", "low", "inconclusive"), '
        '"suggested_fix" (string).'
    )


def baseline_evidence(frames: list[dict]) -> tuple[list[dict], list[dict]]:
    """(context, definitions) in the shape the verifier and scorer expect.

    context: every line of the failing file.
    definitions: the source line the traceback itself prints for each frame in another file.
    """
    failing = frames[-1]
    failing_path = Path(failing["file"])
    try:
        lines = failing_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    context = [{"line": n, "text": text} for n, text in enumerate(lines, start=1)]

    definitions = []
    seen = set()
    failing_resolved = failing_path.resolve()
    for frame in frames[:-1]:
        key = (str(Path(frame["file"]).resolve()), frame["line"])
        if Path(frame["file"]).resolve() == failing_resolved or key in seen:
            continue
        seen.add(key)
        definitions.append(
            {"file": frame["file"], "lines": [{"line": int(frame["line"]), "text": frame["code"]}]}
        )
    return context, definitions
