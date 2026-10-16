"""Readers that turn whatever the PolySwarm client hands back into plain values.

The client returns different shapes depending on the endpoint and on how old
the deployment is, and a playbook must never see a traceback because a counter
arrived as a string or a tag list as a bare name.
"""

from datetime import UTC, datetime
from typing import Any

NUMERIC_ERRORS: tuple[type[Exception], ...] = (TypeError, ValueError)


def as_names(value: Any) -> list[str]:
    """Normalise a families or tags payload into a deduplicated list of names."""
    if isinstance(value, str):
        candidates: list[Any] = [value]
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        return []

    seen: set[str] = set()
    names: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            raw = candidate.get("name") or candidate.get("tag") or candidate.get("family") or ""
        elif isinstance(candidate, str):
            raw = candidate
        else:
            continue
        name = raw.strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def as_number(value: Any) -> int:
    """Read an integer counter, treating anything unreadable as zero."""
    try:
        return int(value)
    except NUMERIC_ERRORS:
        return 0


def as_score(value: Any) -> float | None:
    """Read a polyscore, treating anything unreadable as absent."""
    try:
        return float(value)
    except NUMERIC_ERRORS:
        return None


def as_text(value: Any) -> str:
    """Render a value as plain text, treating an absent value as empty.

    A datetime read off a PolySwarm API result does not always carry a UTC
    offset: the client can hand back a naive value for a field the platform
    itself always reports in UTC. Calling astimezone on a naive datetime does
    not know that, it reads the naive value as the machine's local zone and
    silently shifts it, which is the recurring bug this guards against. A
    naive value is therefore treated as already being UTC (tzinfo attached,
    nothing shifted), and only a value that already carries an offset is
    normalised with astimezone.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    return str(value)


def as_optional_text(value: Any) -> str | None:
    """Render a scalar field as text, keeping an absent value absent rather than empty."""
    if value is None:
        return None
    return str(value)
