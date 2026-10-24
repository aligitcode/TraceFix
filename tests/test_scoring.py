from tracefix.scoring import score_answer

SUFFICIENT = {"cause_file": "cart.py", "cause_line": 2, "evidence_sufficient": True}
INSUFFICIENT = {"cause_file": "lookup.py", "cause_line": 2, "evidence_sufficient": False}
SUPPORTED = {"status": "supported"}


def test_correct_when_it_cites_the_cause_line():
    answer = {"evidence_lines": [2], "confidence": "high"}
    result = score_answer(answer, SUPPORTED, SUFFICIENT, "C:/x/cart.py")
    assert result["correct_behavior"] is True
    assert result["false_confidence"] is False


def test_real_but_irrelevant_line_is_false_confidence():
    answer = {"evidence_lines": [1], "confidence": "high"}
    result = score_answer(answer, SUPPORTED, SUFFICIENT, "C:/x/cart.py")
    assert result["correct_behavior"] is False
    assert result["false_confidence"] is True


def test_confident_answer_when_evidence_is_insufficient_is_wrong():
    answer = {"evidence_lines": [5], "confidence": "high"}
    result = score_answer(answer, SUPPORTED, INSUFFICIENT, "C:/x/run_bug10.py")
    assert result["correct_behavior"] is False
    assert result["false_confidence"] is True


def test_inconclusive_is_correct_when_evidence_is_insufficient():
    answer = {"evidence_lines": [], "confidence": "inconclusive"}
    verification = {"status": "inconclusive"}
    result = score_answer(answer, verification, INSUFFICIENT, "C:/x/run_bug10.py")
    assert result["correct_behavior"] is True
    assert result["false_confidence"] is False


def test_malformed_evidence_lines_are_treated_as_empty():
    answer = {"evidence_lines": "2", "confidence": "high"}
    result = score_answer(answer, {"status": "weak"}, SUFFICIENT, "C:/x/cart.py")
    assert result["cites_cause_line"] is False
    assert result["correct_behavior"] is False
