import time

import pytest

from trendmicro_modules.helpers import iso8601_to_timestamp, unixtime_to_iso8601


@pytest.fixture
def non_utc_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Paris")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_iso8601_to_timestamp_is_utc(non_utc_timezone):
    assert iso8601_to_timestamp("2026-10-26T12:00:00Z") == 1793016000


def test_unixtime_to_iso8601_is_utc(non_utc_timezone):
    assert unixtime_to_iso8601(1793016000) == "2026-10-26T12:00:00Z"


def test_roundtrip(non_utc_timezone):
    assert iso8601_to_timestamp(unixtime_to_iso8601(1793016000)) == 1793016000
