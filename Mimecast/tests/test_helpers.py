from datetime import datetime

import pytest
from cachetools import LRUCache

from mimecast_modules.helpers import get_upper_second, filter_collected_events


def test_get_upper_second():
    starting_datetime = datetime(2022, 12, 11, 23, 45, 26, 208)
    expected_datetime = datetime(2022, 12, 11, 23, 45, 27)

    assert get_upper_second(starting_datetime) == expected_datetime


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
                {"processingId": "key1"},
                {"processingId": "key2"},
                {"processingId": "key3"},
                {"processingId": "key1"},
                {"processingId": "key4"},
                {"key": "key5"},
            ],
            lambda x: x.get("processingId"),
            LRUCache(maxsize=256),
            [{"processingId": "key1"}, {"processingId": "key2"}, {"processingId": "key3"}, {"processingId": "key4"}],
        ),
    ],
)
def test_filter_collected_events(events, getter, cache, expected_list):
    assert filter_collected_events(events, getter, cache) == expected_list
