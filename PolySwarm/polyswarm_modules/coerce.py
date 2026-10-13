"""Readers that turn whatever the PolySwarm client hands back into plain values.

The client returns different shapes depending on the endpoint and on how old
the deployment is, and a playbook must never see a traceback because a counter
arrived as a string or a tag list as a bare name.
"""

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
