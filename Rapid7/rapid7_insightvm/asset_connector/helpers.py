import html
import re
from datetime import datetime, timezone

from dateutil.parser import isoparse

MAX_DESC_LENGTH = 1024
TRUNCATION_SUFFIX = " [...] see more on the Rapid7 InsightVM product"

_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"\s+")
_ESCAPED_UNICODE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; ``None`` when absent or malformed.

    A date without a timezone is read as UTC, so every parsed value can be compared.
    """
    if not value:
        return None
    try:
        parsed = isoparse(value)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_datetime(value: datetime) -> str:
    """Format a timestamp as the API expects it: ``2026-10-28T10:00:00Z`` (UTC, seconds)."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_epoch(value: str | None) -> float | None:
    parsed = parse_datetime(value)
    return parsed.timestamp() if parsed is not None else None


def to_int_epoch(value: str | None) -> int | None:
    epoch = to_epoch(value)
    return int(epoch) if epoch is not None else None


def strip_html(value: str | None) -> str | None:
    """Remove the HTML tags and entities of an InsightVM text and collapse whitespace."""
    if value is None:
        return None
    text = _SPACES_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()
    return text or None


def decode_unicode_escapes(value: str | None) -> str | None:
    """Decode the literal ``\\uXXXX`` sequences some InsightVM descriptions contain."""
    if value is None:
        return None
    return _ESCAPED_UNICODE_RE.sub(lambda match: chr(int(match.group(1), 16)), value)


def truncate(value: str | None, limit: int = MAX_DESC_LENGTH, suffix: str = TRUNCATION_SUFFIX) -> str | None:
    """Trim a text to ``limit`` characters, ending it with ``suffix`` when it is shortened."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) <= limit:
        return trimmed
    if len(suffix) >= limit:
        return trimmed[:limit]
    return trimmed[: limit - len(suffix)] + suffix


def cvss_version(vector: str | None) -> str:
    """Read the CVSS 3.x version from the vector prefix (``CVSS:3.1/...``); "3.0" by default."""
    if vector and vector.upper().startswith("CVSS:"):
        version = vector.split("/", 1)[0].split(":", 1)[1].strip()
        if version:
            return version
    return "3.0"
