import datetime


def iso8601_to_timestamp(dt: str) -> str:
    return str(int(datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ").timestamp()))
