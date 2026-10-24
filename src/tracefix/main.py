import re
from pathlib import Path


def summarize_error(error_text: str) -> dict[str, str]:
    """Extract a basic summary from a Python error message."""
    lines = [line.strip() for line in error_text.strip().splitlines() if line.strip()]

    if not lines:
        return {
            "error_type": "Unknown",
            "message": "No error message provided",
        }

    last_line = lines[-1]

    if ":" in last_line:
        error_type, message = last_line.split(":", 1)
        return {
            "error_type": error_type.strip(),
            "message": message.strip(),
        }

    return {
        "error_type": "Unknown",
        "message": last_line,
    }


FRAME_PATTERN = re.compile(r'^File "(.+)", line (\d+), in (.+)$')


def parse_frames(error_text: str) -> list[dict[str, str]]:
    """Extract each file/line/function step from a Python traceback."""
    lines = [line.strip() for line in error_text.strip().splitlines()]
    frames = []

    for index, line in enumerate(lines):
        match = FRAME_PATTERN.match(line)
        if match:
            code = lines[index + 1] if index + 1 < len(lines) else ""
            frames.append(
                {
                    "file": match.group(1),
                    "line": match.group(2),
                    "function": match.group(3),
                    "code": code,
                }
            )

    return frames


def get_code_context(file_path: str, line_number: int, radius: int = 3) -> list[dict]:
    """Return the lines of code around a given line number."""
    path = Path(file_path)
    if not path.is_file():
        return []

    source_lines = path.read_text(encoding="utf-8").splitlines()
    start = max(line_number - radius, 1)
    end = min(line_number + radius, len(source_lines))

    return [{"line": n, "text": source_lines[n - 1]} for n in range(start, end + 1)]