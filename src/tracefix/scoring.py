from pathlib import Path


def score_answer(answer: dict, verification: dict, case: dict, failing_file: str) -> dict:
    """Score one Gemini answer against the answer key.

    If the evidence is sufficient, the answer is correct only when it cites
    the line where the defect actually is. If the evidence is not sufficient,
    the correct behaviour is to answer with low or inconclusive confidence.

    A plain number means a line of the failing file; "file.py:line" is a
    file-qualified citation.

    This scores the cited lines and the confidence only. It does not judge
    whether the written explanation is right; that needs a manual review.
    """
    sufficient = case.get("evidence_sufficient", True)

    cited = answer.get("evidence_lines", [])
    if not isinstance(cited, list):
        cited = []
    confidence = answer.get("confidence")

    cause_ref = f"{case['cause_file']}:{case['cause_line']}"
    cited_strings = [c.strip() for c in cited if isinstance(c, str)]
    cites_cause = cause_ref in cited_strings or (
        Path(failing_file).name == case["cause_file"] and case["cause_line"] in cited
    )

    if sufficient:
        correct = cites_cause
    else:
        correct = confidence in ("low", "inconclusive")

    return {
        "status": verification["status"],
        "confidence": confidence,
        "cites_cause_line": cites_cause,
        "correct_behavior": correct,
        "false_confidence": verification["status"] == "supported" and not correct,
    }
