from datetime import datetime, timezone

import pytest
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat

from sentinelone_module.logs.helpers import get_latest_event_timestamp


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
    ],
)
def test_get_lastest_event_timestamp(events, expected_datetime):
    assert get_latest_event_timestamp(events) == expected_datetime

def test_get_latest_event_timestamp_no_valid_timestamps():
    """Test that a ValueError is raised when no valid timestamps are found."""
    with pytest.raises(ValueError, match="No valid event timestamps found in the provided list."):
        get_latest_event_timestamp([{}, {}, {}])

def test_get_latest_event_timestamp_empty_list():
    """Test that a ValueError is raised when the list is empty."""
    with pytest.raises(ValueError, match="No valid event timestamps found in the provided list."):
        get_latest_event_timestamp([])
