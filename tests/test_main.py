
from tracefix.main import summarize_error


def test_summarize_value_error():
    result = summarize_error("ValueError: invalid input")

    assert result["error_type"] == "ValueError"
    assert result["message"] == "invalid input"


def test_empty_error():
    result = summarize_error("")

    assert result["error_type"] == "Unknown"
    assert result["message"] == "No error message provided"


def test_error_with_traceback():
    error_text = """Traceback (most recent call last):
  File "example.py", line 10, in main
    raise ValueError("invalid input")
ValueError: invalid input"""

    result = summarize_error(error_text)

    assert result["error_type"] == "ValueError"
    assert result["message"] == "invalid input"
