import pytest

from sophos_module.helper import (
    extract_info,
    latest_timestamp,
    normalize_xdr_message,
    parse_iso8601_timestamp,
    strip_null_values,
    translate_fields,
)


def test_translate_fields():
    assert translate_fields({"name": "name", "source": "source", "created_at": "created_at"}) == {
        "name": "name",
        "suser": "source",
        "rt": "created_at",
    }


def test_translate_fields_with_created_at_camel_case():
    assert translate_fields({"name": "name", "source": "source", "createdAt": "createdAt"}) == {
        "name": "name",
        "suser": "source",
        "rt": "createdAt",
    }


def test_strip_null_values():
    assert strip_null_values({"name1": "value1", "name2": None, "name3": "value3"}) == {
        "name1": "value1",
        "name3": "value3",
    }


def test_parse_iso8601_timestamp_handles_invalid_values():
    assert parse_iso8601_timestamp(None) is None
    assert parse_iso8601_timestamp(123) is None
    assert parse_iso8601_timestamp("") is None
    assert parse_iso8601_timestamp("not-a-date") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2023-07-03T11:28:45.000Z", 1688383725.0),
        ("2023-07-03T11:28:45.000z", 1688383725.0),
        ("2023-07-03T13:28:45+02:00", 1688383725.0),
        ("2023-07-03T11:28:45+0000", 1688383725.0),
        ("2023-07-03T11:28:45.123456789Z", 1688383725.123456),
        ("2023-07-03T11:28:45", 1688383725.0),
    ],
)
def test_parse_iso8601_timestamp_exact_values(raw, expected):
    assert parse_iso8601_timestamp(raw) == expected


def test_latest_timestamp_uses_first_parseable_key_per_item():
    assert (
        latest_timestamp(
            [
                {"created_at": "invalid", "createdAt": "2023-07-03T11:28:45Z"},
                {"created_at": "2023-07-03T11:29:45Z", "createdAt": "2023-07-03T12:28:45Z"},
                {"created_at": None},
            ],
            ("created_at", "createdAt"),
        )
        == 1688383785.0
    )
    assert latest_timestamp([], ("created_at",)) is None
    assert latest_timestamp([{"created_at": "invalid"}], ("created_at",)) is None


def test_normalize_xdr_preserves_existing_calendar_time():
    row = {"calendar_time": "original", "calendarTime": "alias", "ioc_severity": 4}
    assert normalize_xdr_message(row) == {"calendar_time": "original", "ioc_severity": 4}
    assert row["calendarTime"] == "alias"


def test_extract_info():
    assert extract_info(
        {
            "type": "Event::Endpoint::Threat::CleanedUp",
            "name": "Threat 'EICAR' in 'myfile.com' ",
        }
    ) == {
        "type": "Event::Endpoint::Threat::CleanedUp",
        "name": "EICAR",
        "filePath": "myfile.com",
        "detection_identity_name": "EICAR",
    }

    assert extract_info(
        {
            "type": "Event::Endpoint::DataLossPreventionUserAllowed",
            "name": "An \u2033allow transfer on acceptance by user\u2033 action was taken.  "
            "Username: WIN10CLOUD2\\Sophos  Rule names: \u2032test\u2032  User action: File open  "
            "Application Name: Google Chrome  Data Control action: Allow  "
            "File type: Plain text (ASCII/UTF-8)  File size: 36  "
            "Source path: C:\\Users\\Sophos\\Desktop\\test.txt",
        }
    ) == {
        "type": "Event::Endpoint::DataLossPreventionUserAllowed",
        "name": "allow transfer on acceptance by user",
        "user": "WIN10CLOUD2\\Sophos",
        "rule": "test",
        "user_action": "File open",
        "app_name": "Google Chrome",
        "action": "Allow",
        "file_type": "Plain text (ASCII/UTF-8)",
        "file_size": "36",
        "file_path": "C:\\Users\\Sophos\\Desktop\\test.txt",
    }
