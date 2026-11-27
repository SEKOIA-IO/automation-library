import pytest

from sophos_module.helper import (
    extract_info,
    latest_timestamp,
    normalize_message,
    parse_iso8601_timestamp,
    strip_null_values,
    translate_fields,
)


@pytest.mark.parametrize(
    "data, expected",
    [
        pytest.param(
            {"name": "name", "source": "source", "created_at": "created_at"},
            {"name": "name", "suser": "source", "rt": "created_at"},
            id="mapped-fields",
        ),
        pytest.param(
            {"when": "w", "user_id": "u", "location": "l", "id": "1"},
            {"end": "w", "duid": "u", "dhost": "l", "id": "1"},
            id="unmapped-fields-are-kept",
        ),
        pytest.param({}, {}, id="empty"),
    ],
)
def test_translate_fields(data, expected):
    assert translate_fields(data) == expected


@pytest.mark.parametrize(
    "data, expected",
    [
        pytest.param({"a": "1", "b": None, "c": "3"}, {"a": "1", "c": "3"}, id="null-values"),
        pytest.param({"a": 0, "b": "", "c": False}, {"a": 0, "b": "", "c": False}, id="falsy-values-are-kept"),
        pytest.param({"a": None}, {}, id="only-nulls"),
    ],
)
def test_strip_null_values(data, expected):
    assert strip_null_values(data) == expected


def test_normalize_message():
    message = {
        "type": "Event::Endpoint::Threat::Detected",
        "name": "Malware detected: 'Eicar-AV-Test' at 'C:\\eicar.com'",
        "created_at": "2019-04-01T15:11:41.053Z",
        "source": "n/a",
        "origin": None,
    }

    assert normalize_message(message) == {
        "type": "Event::Endpoint::Threat::Detected",
        "name": "Eicar-AV-Test",
        "detection_identity_name": "Eicar-AV-Test",
        "filePath": "C:\\eicar.com",
        "rt": "2019-04-01T15:11:41.053Z",
        "suser": "n/a",
    }


@pytest.mark.parametrize(
    "data, expected",
    [
        pytest.param(
            {"type": "Event::Endpoint::Threat::CleanedUp", "name": "Threat 'EICAR' in 'myfile.com' "},
            {
                "type": "Event::Endpoint::Threat::CleanedUp",
                "name": "EICAR",
                "filePath": "myfile.com",
                "detection_identity_name": "EICAR",
            },
            id="threat",
        ),
        pytest.param(
            {
                "type": "Event::Endpoint::DataLossPreventionUserAllowed",
                "name": "An \u2033allow transfer on acceptance by user\u2033 action was taken.  "
                "Username: WIN10CLOUD2\\Sophos  Rule names: \u2032test\u2032  User action: File open  "
                "Application Name: Google Chrome  Data Control action: Allow  "
                "File type: Plain text (ASCII/UTF-8)  File size: 36  "
                "Source path: C:\\Users\\Sophos\\Desktop\\test.txt",
            },
            {
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
            },
            id="data-loss-prevention",
        ),
        pytest.param(
            {"type": "Event::Endpoint::Threat::Detected", "description": "Threat 'X' in 'a.exe'", "name": "ignored"},
            {
                "type": "Event::Endpoint::Threat::Detected",
                "description": "Threat 'X' in 'a.exe'",
                "name": "X",
                "filePath": "a.exe",
                "detection_identity_name": "X",
            },
            id="description-replaces-name",
        ),
        pytest.param(
            {"type": "Event::Endpoint::Threat::Detected", "name": "no quoted parts"},
            {"type": "Event::Endpoint::Threat::Detected", "name": "no quoted parts"},
            id="regex-without-match",
        ),
        pytest.param(
            {"type": "Event::Endpoint::Registered", "name": "New server registered"},
            {"type": "Event::Endpoint::Registered", "name": "New server registered"},
            id="type-without-regex",
        ),
        pytest.param({"name": "no type"}, {"name": "no type"}, id="no-type"),
    ],
)
def test_extract_info(data, expected):
    assert extract_info(data) == expected


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
        ("2023-07-03T11:28:45Z", 1688383725.0),
        ("2023-07-03T13:28:45+02:00", 1688383725.0),
        ("2023-07-03T11:28:45", 1688383725.0),
    ],
)
def test_parse_iso8601_timestamp_exact_values(raw, expected):
    assert parse_iso8601_timestamp(raw) == expected


@pytest.mark.parametrize(
    "items, expected",
    [
        pytest.param(
            [
                {"created_at": "invalid", "when": "2023-07-03T11:28:45Z"},
                {"created_at": "2023-07-03T11:29:45Z", "when": "2023-07-03T12:28:45Z"},
                {"created_at": None},
            ],
            1688383785.0,
            id="first-parseable-key-per-item",
        ),
        pytest.param(
            [{"created_at": "2023-07-03T11:29:45Z"}, {"created_at": "2023-07-03T11:28:45Z"}],
            1688383785.0,
            id="older-item-last",
        ),
        pytest.param([], None, id="no-items"),
        pytest.param([{"created_at": "invalid"}], None, id="no-parseable-date"),
    ],
)
def test_latest_timestamp(items, expected):
    assert latest_timestamp(items, ("created_at", "when")) == expected
