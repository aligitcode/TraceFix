from tracefix.main import summarize_error


def test_summarize_error_basic():
    text = "Traceback (most recent call last):\n  File x.py\nValueError: bad input"
    result = summarize_error(text)
    assert result["error_type"] == "ValueError"
    assert result["message"] == "bad input"


def test_summarize_error_empty():
    assert summarize_error("")["error_type"] == "Unknown"