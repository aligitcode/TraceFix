def verify_report(report: dict, context: list[dict]) -> dict:
    """Check that the lines Gemini cites really exist in the evidence."""
    valid_lines = {item["line"] for item in context}

    cited = report.get("evidence_lines", [])
    if not isinstance(cited, list):
        cited = []

    valid = [n for n in cited if isinstance(n, int) and n in valid_lines]
    invalid = [n for n in cited if not (isinstance(n, int) and n in valid_lines)]

    if report.get("confidence") == "inconclusive":
        status = "inconclusive"
    elif not valid or invalid:
        status = "weak"
    else:
        status = "supported"

    return {"status": status, "valid_lines": valid, "invalid_lines": invalid}
