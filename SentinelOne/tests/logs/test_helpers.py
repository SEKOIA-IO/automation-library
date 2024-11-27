from datetime import datetime, timezone

import pytest
from cachetools import LRUCache
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat

from sentinelone_module.logs.helpers import filter_collected_events, get_latest_event_timestamp


@pytest.mark.parametrize(
    "events,expected_datetime",
    [
        (
            [
                Activity(createdAt="2024-07-21T11:23:48Z"),
                Activity(createdAt="2024-07-25T02:30:11Z"),
                Activity(createdAt="2024-07-22T14:56:11Z"),
            ],
            datetime(2024, 7, 25, 2, 30, 11, tzinfo=timezone.utc),
        ),
        (
            [
                Threat(createdAt="2024-07-21T11:23:48Z"),
                Threat(createdAt="2024-07-25T02:30:11Z"),
                Threat(createdAt="2024-07-22T14:56:11Z"),
            ],
            datetime(2024, 7, 25, 2, 30, 11, tzinfo=timezone.utc),
        ),
        (
            [
                dict(createdAt="2024-07-21T11:23:48Z"),
                dict(createdAt="2024-07-25T02:30:11Z"),
                dict(createdAt="2024-07-22T14:56:11Z"),
            ],
            datetime(2024, 7, 25, 2, 30, 11, tzinfo=timezone.utc),
        ),
        ([{}, {}, {}], None),
        ([], None),
    ],
)
def test_get_lastest_event_timestamp(events, expected_datetime):
    assert get_latest_event_timestamp(events) == expected_datetime


@pytest.mark.parametrize(
    "events,getter,cache,expected_list",
    [
        (
            ["key1", "key2", "key3", "key2", "key4"],
            lambda x: x,
            LRUCache(maxsize=256),
            ["key1", "key2", "key3", "key4"],
        ),
        ([], lambda x: x, LRUCache(maxsize=256), []),
        (["key1", "key2", "key3", "key4"], lambda x: x, LRUCache(maxsize=256), ["key1", "key2", "key3", "key4"]),
        (
            [
                {"name": "key1"},
                {"name": "key2"},
                {"name": "key3"},
                {"name": "key1"},
                {"name": "key4"},
                {"key": "key5"},
            ],
            lambda x: x.get("name"),
            LRUCache(maxsize=256),
            [{"name": "key1"}, {"name": "key2"}, {"name": "key3"}, {"name": "key4"}],
        ),
    ],
)
def test_filter_collected_events(events, getter, cache, expected_list):
    assert filter_collected_events(events, getter, cache) == expected_list
