"""Shared test data builders (timestamps relative to now, finding variants)."""

from datetime import UTC, datetime, timedelta

DAY = 86400
T1 = int((datetime.now(UTC) - timedelta(days=5)).timestamp())
T2 = T1 + DAY
T3 = T2 + DAY
T5 = T3 + 2 * DAY


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def sdk_iso(ts: int) -> str:
    """Format written by the CheckpointTimestamp used up to 1.0.19."""
    return datetime.fromtimestamp(ts).astimezone(UTC).isoformat()


def make_vuln(
    base: dict, finding_id: str, last_found: int, state: str = "OPEN", last_fixed: int | None = None
) -> dict:
    vuln = {
        **base,
        "finding_id": finding_id,
        "state": state,
        "first_found": iso(last_found),
        "last_found": iso(last_found),
    }
    if last_fixed is not None:
        vuln["last_fixed"] = iso(last_fixed)
    return vuln
