import pytest

from trendmicro_modules.helpers import iso8601_to_timestamp, unixtime_to_iso8601


@pytest.mark.parametrize(
    ("iso8601_value", "timestamp_value"),
    [
        ("1970-01-01T00:00:00Z", 0),
        ("2026-01-10T12:13:14Z", 1768047194),
    ],
)
def test_iso8601_timestamp_conversion(iso8601_value, timestamp_value):
    assert iso8601_to_timestamp(iso8601_value) == timestamp_value
    assert unixtime_to_iso8601(timestamp_value) == iso8601_value


def test_roundtrip_timestamp_and_iso8601():
    value = "2026-01-10T12:13:14Z"
    assert unixtime_to_iso8601(iso8601_to_timestamp(value)) == value
