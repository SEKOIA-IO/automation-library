import datetime


def iso8601_to_timestamp(dt: str) -> int:
    # genTime may contain fractional seconds (e.g. 2026-10-26T12:00:00.123Z): truncate them to the second
    parsed = datetime.datetime.fromisoformat(dt)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)

    return int(parsed.timestamp())


def unixtime_to_iso8601(timestamp: int) -> str:
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
