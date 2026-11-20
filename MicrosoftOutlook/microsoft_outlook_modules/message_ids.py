"""Translate normalized SIEM identifiers to Internet Message-ID syntax."""

from .errors import ActionInputError


def graph_message_id(value: str) -> str:
    """Accept either representation, preserve case and reject malformed delimiters."""
    value = value.strip()
    if not value or any(character in value for character in "\r\n"):
        raise ActionInputError("Use a non-empty, single-line Internet Message-ID.", field="email_message_id")
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    if not value or any(character in value for character in "<>\r\n"):
        raise ActionInputError(
            "Use id@example.com or <id@example.com>; angle brackets must form a single matching pair.",
            field="email_message_id",
        )
    return f"<{value}>"
