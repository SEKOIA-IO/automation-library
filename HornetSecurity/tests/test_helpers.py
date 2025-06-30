from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.storage import PersistentJSON

from hornetsecurity_modules.helpers import (
    ApiError,
    has_more_emails,
    load_events_cache,
    normalize_uri,
    range_offset_limit,
    remove_duplicates,
    save_events_cache,
    utc_zulu_format,
)


def test_api_error_from_response():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.return_value = {
        "error_id": "123",
        "error_data": "Some data",
        "error_message": "An error occurred",
    }

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "123"
    assert api_error.data == "Some data"
    assert api_error.message == "An error occurred"


def test_api_error_from_response_without_details():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.return_value = {}

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "N/A"
    assert api_error.data == "N/A"
    assert api_error.message == "Unknown error"


def test_api_error_from_response_with_invalid_details():
    mock_response = Mock(spec=requests.Response)
    mock_response.status_code = 404
    mock_response.reason = "Not Found"
    mock_response.json.side_effect = ValueError("invalid json")

    api_error = ApiError.from_response_error(mock_response)

    assert api_error.status_code == 404
    assert api_error.reason == "Not Found"
    assert api_error.id == "N/A"
    assert api_error.data == "N/A"
    assert api_error.message == "Unknown error"


@pytest.mark.parametrize(
    "dt, expected",
    [
        (datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc), "2023-10-01T12:00:00Z"),
        (
            datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5))),
            "2023-10-01T17:00:00Z",
        ),
    ],
)
def test_utc_zulu_format(dt, expected):
    formatted_date = utc_zulu_format(dt)
    assert formatted_date == expected


def test_save_events_cache(data_storage):
    context = PersistentJSON("cache.json", data_storage)
    events_cache = {"event1": True, "event2": True}

    save_events_cache(events_cache, context)

    with context as cache:
        saved_cache = cache.get("events_cache", [])

    assert saved_cache == list(events_cache.keys())


def test_load_events_cache(data_storage):
    context = PersistentJSON("cache.json", data_storage)
    events_cache = {"event1": True, "event2": True}

    with context as cache:
        cache["events_cache"] = list(events_cache.keys())

    loaded_cache = load_events_cache(context)

    assert len(loaded_cache) == len(events_cache)
    assert "event1" in loaded_cache
    assert "event2" in loaded_cache


def test_remove_duplicates():
    events = [
        {"id": "event1", "data": "data1"},  # already in cache
        {"id": "event2", "data": "data2"},
        {"id": "event3", "data": "data1"},
        {"id": "event2", "data": "data1"},  # duplicate
    ]
    events_cache = {"event1": True}

    unique_events = remove_duplicates(events, events_cache, "id")

    assert len(unique_events) == 2
    assert unique_events[0]["id"] == "event2"
    assert unique_events[1]["id"] == "event3"


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("http://example.com/", "https://example.com"),
        ("https://example.com/path", "https://example.com/path"),
        ("example.com:8080", "https://example.com:8080"),
    ],
)
def test_normalize_uri(uri, expected):
    normalized_uri = normalize_uri(uri)
    assert normalized_uri == expected


def test_range_offset_limit():
    offset = 10
    limit = 5
    ranges = range_offset_limit(offset, limit)

    assert next(ranges) == (10, 5)
    assert next(ranges) == (15, 5)
    assert next(ranges) == (20, 5)


@pytest.mark.parametrize(
    "total_emails, offset, limit, expected",
    [
        (100, 0, 90, True),  # Has more elements
        (90, 0, 100, False),  # Reached the limit
        (130, 0, 130, False),  # Reached the limit
        (130, 130, 130, False),  # Reached the limit
    ],
)
def test_has_more_emails(total_emails: int, offset: int, limit: int, expected: bool):
    result = has_more_emails(total_emails, offset, limit)
    assert result == expected
