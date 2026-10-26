import datetime


def iso8601_to_timestamp(dt: str) -> int:
    return int(datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp())


def unixtime_to_iso8601(timestamp: int) -> str:
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
