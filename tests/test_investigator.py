from tracefix.investigator import build_prompt


def test_build_prompt_contains_evidence():
    summary = {"error_type": "ZeroDivisionError", "message": "division by zero"}
    frame = {"file": "cart.py", "line": "2", "function": "average_price"}
    context = [{"line": 2, "text": "return sum(prices) / len(prices)"}]
    prompt = build_prompt(summary, frame, context)
    assert "ZeroDivisionError" in prompt
    assert "2: return sum(prices) / len(prices)" in prompt
