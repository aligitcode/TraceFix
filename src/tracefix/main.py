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