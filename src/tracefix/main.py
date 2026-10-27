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

def find_called_definitions(context: list[dict], search_dir: str) -> list[dict]:
    """Find project functions called in the context lines and return their code."""
    import ast
    import builtins

    names = set()
    for item in context:
        for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", item["text"]):
            if not hasattr(builtins, name):
                names.add(name)

    found = []
    for path in sorted(Path(search_dir).glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue
        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in names:
                found.append(
                    {
                        "name": node.name,
                        "file": str(path),
                        "start": node.lineno,
                        "end": node.end_lineno,
                        "lines": [
                            {"line": n, "text": source_lines[n - 1]}
                            for n in range(node.lineno, node.end_lineno + 1)
                        ],
                    }
                )
    return found


def get_frame_contexts(frames: list[dict], radius: int = 3) -> list[dict]:
    """Code around every frame except the last, for files that exist."""
    out = []
    seen = set()
    failing_file = str(Path(frames[-1]["file"]).resolve()) if frames else ""
    for frame in frames[:-1]:
        resolved = str(Path(frame["file"]).resolve())
        key = (resolved, frame["line"])
        if resolved == failing_file or key in seen:
            continue
        seen.add(key)
        ctx = get_code_context(frame["file"], int(frame["line"]), radius)
        if ctx:
            out.append({"file": frame["file"], "function": frame["function"], "lines": ctx})
    return out


def find_imported_constants(file_path: str) -> list[dict]:
    """Top-level simple assignments (NAME = literal) in local modules imported by file_path."""
    import ast

    path = Path(file_path)
    if not path.is_file():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    wanted = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            wanted.setdefault(node.module, set()).update(a.name for a in node.names)

    found = []
    for module, names in wanted.items():
        mod_path = path.parent / f"{module}.py"
        if not mod_path.is_file():
            continue
        source = mod_path.read_text(encoding="utf-8")
        lines = source.splitlines()
        try:
            mod_tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in mod_tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in names for t in node.targets
            ):
                found.append({
                    "file": str(mod_path),
                    "lines": [{"line": n, "text": lines[n - 1]} for n in range(node.lineno, node.end_lineno + 1)],
                })
    return found
