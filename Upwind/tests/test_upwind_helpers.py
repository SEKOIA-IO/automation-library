from datetime import UTC, datetime

import pytest
from cachetools import LRUCache

import upwind
from upwind import extract_upwind_detection_datetime, filter_new_events


def test_extract_detection_datetime_prefers_last_seen_time() -> None:
    event = {
        "first_seen_time": "2026-01-31T03:03:11Z",
        "last_seen_time": "2026-02-16T09:06:02Z",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 2, 16, 9, 6, 2, tzinfo=UTC)


def test_extract_detection_datetime_fallbacks_to_first_seen_time() -> None:
    event = {
        "first_seen_time": "2026-03-17T11:58:50Z",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 3, 17, 11, 58, 50, tzinfo=UTC)


def test_filter_new_events_deduplicates_by_id() -> None:
    cache = LRUCache(maxsize=100)

    events = [
        {"id": "uwd-11111111111111aa", "category": "CLOUD_TRAIL"},
        {"id": "uwd-11111111111111aa", "category": "CLOUD_TRAIL"},
        {"id": "uwd-22222222222222bb", "category": "API_SECURITY"},
    ]

    selected = filter_new_events(events, cache)

    assert [event["id"] for event in selected] == [
        "uwd-11111111111111aa",
        "uwd-22222222222222bb",
    ]


def test_extract_detection_datetime_handles_naive_timestamp() -> None:
    event = {
        "last_seen_time": "2026-04-10T14:05:00",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 4, 10, 14, 5, 0, tzinfo=UTC)


def test_extract_detection_datetime_skips_invalid_last_seen_and_uses_first_seen() -> None:
    event = {
        "last_seen_time": "not-a-date",
        "first_seen_time": "2026-05-01T12:00:00Z",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


def test_extract_detection_datetime_ignores_non_datetime_parsed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_isoparse(value: str) -> datetime | str:
        if value == "not-datetime":
            return "unexpected"
        return datetime(2026, 6, 1, 8, 0, 0)

    monkeypatch.setattr(upwind, "isoparse", fake_isoparse)

    event = {
        "last_seen_time": "not-datetime",
        "first_seen_time": "2026-06-01T08:00:00",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC)


def test_filter_new_events_skips_entries_without_id() -> None:
    cache = LRUCache(maxsize=10)
    events = [{"category": "no-id"}, {"id": "uwd-33333333333333cc"}]

    selected = filter_new_events(events, cache)

    assert [event["id"] for event in selected] == ["uwd-33333333333333cc"]
