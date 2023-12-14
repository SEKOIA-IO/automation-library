from datetime import datetime, timedelta, timezone

from proofpoint_modules.helpers import format_datetime, normalize_since_time, parse_user_date


def test_format_datetime():
    assert format_datetime(datetime(2050, 9, 1, 12, 45, 23, tzinfo=timezone.utc)) == "2050-09-01T12:45:23.000000Z"


def test_normalize_since_time():
    now = datetime.now(timezone.utc)
    assert normalize_since_time(None) >= now - timedelta(minutes=1)
    assert normalize_since_time("2050-09-01T13:45:23+01:00") == datetime(2050, 9, 1, 12, 45, 23, tzinfo=timezone.utc)
    assert normalize_since_time("2021-09-01T13:45:23+01:00") > now - timedelta(days=30)
    assert normalize_since_time("2021-09-01") > now - timedelta(days=30)


def test_parse_user_date():
    assert parse_user_date("2050-09-01T13:45:23+01:00") == datetime(
        2050, 9, 1, 13, 45, 23, tzinfo=timezone(timedelta(hours=1))
    )
    assert parse_user_date("2050-09-01T12:45:23+00:00") == datetime(2050, 9, 1, 12, 45, 23, tzinfo=timezone.utc)
    assert parse_user_date("2050-09-01") == datetime(2050, 9, 1, tzinfo=timezone.utc)
    assert parse_user_date("") == None
    assert parse_user_date(None) == None
