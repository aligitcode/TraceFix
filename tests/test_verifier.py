from tracefix.verifier import verify_report

CONTEXT = [{"line": 1, "text": "a"}, {"line": 2, "text": "b"}]


def test_supported_when_all_lines_exist():
    result = verify_report({"evidence_lines": [2], "confidence": "high"}, CONTEXT)
    assert result["status"] == "supported"


def test_weak_when_a_line_is_invented():
    result = verify_report({"evidence_lines": [2, 99], "confidence": "high"}, CONTEXT)
    assert result["status"] == "weak"
    assert result["invalid_lines"] == [99]


def test_weak_when_no_evidence_is_cited():
    result = verify_report({"evidence_lines": [], "confidence": "high"}, CONTEXT)
    assert result["status"] == "weak"


def test_inconclusive_is_respected():
    result = verify_report({"evidence_lines": [], "confidence": "inconclusive"}, CONTEXT)
    assert result["status"] == "inconclusive"
