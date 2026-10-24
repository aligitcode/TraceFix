from tracefix.main import summarize_error, parse_frames


def test_summarize_error_basic():
    text = "Traceback (most recent call last):\n  File x.py\nValueError: bad input"
    result = summarize_error(text)
    assert result["error_type"] == "ValueError"
    assert result["message"] == "bad input"


def test_summarize_error_empty():
    assert summarize_error("")["error_type"] == "Unknown"


def test_parse_frames():
    text = (
        "Traceback (most recent call last):\n"
        '  File "run.py", line 3, in <module>\n'
        "    print(average_price([]))\n"
        '  File "cart.py", line 2, in average_price\n'
        "    return sum(prices) / len(prices)\n"
        "ZeroDivisionError: division by zero\n"
    )
    frames = parse_frames(text)
    assert len(frames) == 2
    assert frames[-1]["file"] == "cart.py"
    assert frames[-1]["line"] == "2"
    assert frames[-1]["function"] == "average_price"