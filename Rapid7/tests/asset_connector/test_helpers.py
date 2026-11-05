from datetime import datetime, timedelta, timezone

import pytest

from rapid7_insightvm.asset_connector import helpers


def test_strip_html_and_truncate():
    assert helpers.strip_html("<p><ul><li>A &amp; B</li>\n<li>C</li></ul></p>") == "A & B C"
    assert helpers.strip_html("<p></p>") is None
    assert helpers.strip_html(None) is None
    assert helpers.truncate("  short  ") == "short"
    assert helpers.truncate("   ") is None
    assert helpers.truncate(None) is None
    long = helpers.truncate("x" * 2000)
    assert len(long) == 1024 and long.endswith(helpers.TRUNCATION_SUFFIX)
    assert helpers.truncate("abcdef", limit=3, suffix="toolong") == "abc"


def test_decode_unicode_escapes():
    assert helpers.decode_unicode_escapes("Plugin \\u2013 100% FREE") == "Plugin – 100% FREE"
    assert helpers.decode_unicode_escapes(None) is None


def test_dates():
    assert helpers.parse_datetime("2026-10-13T15:04:28.719Z") == datetime(
        2026, 10, 13, 15, 4, 28, 719000, tzinfo=timezone.utc
    )
    assert helpers.parse_datetime("2026-10-13T15:04:28").tzinfo == timezone.utc
    assert helpers.parse_datetime("not a date") is None
    assert helpers.parse_datetime(None) is None
    assert helpers.to_int_epoch("1970-01-01T00:01:00Z") == 60
    assert helpers.to_epoch(None) is None
    assert helpers.format_datetime(datetime(2026, 10, 28, 13, 0, 5, 123, tzinfo=timezone(timedelta(hours=2)))) == (
        "2026-10-28T11:00:05Z"
    )


@pytest.mark.parametrize(
    "vector, expected",
    [
        ("CVSS:3.1/AV:N/AC:H", "3.1"),
        ("CVSS:3.0/AV:N", "3.0"),
        ("CVSS:/AV:N", "3.0"),
        ("AV:N/AC:H", "3.0"),
        (None, "3.0"),
    ],
)
def test_cvss_version(vector, expected):
    assert helpers.cvss_version(vector) == expected
