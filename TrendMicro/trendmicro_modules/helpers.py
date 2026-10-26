import datetime


def iso8601_to_timestamp(dt: str) -> int:
    return int(datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.UTC).timestamp())


def unixtime_to_iso8601(timestamp: int) -> str:
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
