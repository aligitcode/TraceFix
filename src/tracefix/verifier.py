from pathlib import Path


def verify_report(
    report: dict,
    context: list[dict],
    definitions: list[dict] | None = None,
    failing_file: str | None = None,
) -> dict:
    """Check that the lines Gemini cites really exist in the evidence.

    A plain number refers to the failing file. A string "file.py:line" refers
    to a file-qualified line (the failing file or a called function).
    """
    valid_keys = {item["line"] for item in context}
    if failing_file:
        name = Path(failing_file).name
        valid_keys |= {f"{name}:{item['line']}" for item in context}
    for d in definitions or []:
        name = Path(d["file"]).name
        valid_keys |= {f"{name}:{l['line']}" for l in d["lines"]}

    cited = report.get("evidence_lines", [])
    if not isinstance(cited, list):
        cited = []

    def is_valid(n):
        if isinstance(n, bool) or not isinstance(n, (int, str)):
            return False
        return (n.strip() if isinstance(n, str) else n) in valid_keys

    valid = [n for n in cited if is_valid(n)]
    invalid = [n for n in cited if not is_valid(n)]

    if report.get("confidence") == "inconclusive":
        status = "inconclusive"
    elif not valid or invalid:
        status = "weak"
    else:
        status = "supported"

    return {"status": status, "valid_lines": valid, "invalid_lines": invalid}
