from datetime import datetime, timedelta, timezone

from proofpoint_modules.helpers import format_datetime, normalize_since_time


def test_format_datetime():
    assert format_datetime(datetime(2050, 9, 1, 12, 45, 23, tzinfo=timezone.utc)) == "2050-09-01T12:45:23.000000Z"


def test_normalize_since_time():
    now = datetime.now(timezone.utc)
    assert normalize_since_time(None) >= now - timedelta(minutes=1)
    assert normalize_since_time("2050-09-01T13:45:23+01:00") == datetime(2050, 9, 1, 12, 45, 23, tzinfo=timezone.utc)
    assert normalize_since_time("2021-09-01T13:45:23+01:00") > now - timedelta(days=30)
