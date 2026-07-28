from datetime import UTC, datetime

from cachetools import LRUCache

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
