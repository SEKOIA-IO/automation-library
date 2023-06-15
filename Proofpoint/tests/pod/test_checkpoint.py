from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from dateutil.parser import isoparse
from sekoia_automation.storage import PersistentJSON

from proofpoint_modules.pod.checkpoint import Checkpoint


@pytest.fixture
def checkpoint(symphony_storage):
    return Checkpoint(symphony_storage)


def test_load(checkpoint, symphony_storage):
    date = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_seen"] = most_recent_date_requested.isoformat()

    with patch("proofpoint_modules.pod.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert checkpoint.offset == most_recent_date_requested


def test_load_with_cursor_older_than_30_days(checkpoint, symphony_storage):
    date = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
    most_recent_date_requested = date - timedelta(days=40)
    expected_date = date - timedelta(days=30)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_seen"] = most_recent_date_requested.isoformat()

    with patch("proofpoint_modules.pod.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert checkpoint.offset == expected_date


def test_load_without_cursor(checkpoint, symphony_storage):
    context = PersistentJSON("context.json", symphony_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_seen"] = None

    with patch("proofpoint_modules.pod.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert checkpoint.offset is None


def test_save_without_cursor(checkpoint, symphony_storage):
    last_message_date_str = "2023-04-27T11:34:56+00:00"
    most_recent_date_seen_str = None

    # set the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        cache["most_recent_date_seen"] = most_recent_date_seen_str

    checkpoint.offset = isoparse(last_message_date_str)

    # assert the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        assert cache["most_recent_date_seen"] == last_message_date_str


def test_save_replace_existing_date(checkpoint, symphony_storage):
    with patch("proofpoint_modules.pod.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 5, 11, 13, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        last_message_date_str = "2023-04-27T11:34:56+00:00"
        most_recent_date_seen_str = "2023-04-27T09:45:32+00:00"

        # set the cursor
        context = PersistentJSON("context.json", symphony_storage)
        with context as cache:
            cache["most_recent_date_seen"] = most_recent_date_seen_str

        checkpoint.offset = isoparse(last_message_date_str)

        # assert the cursor
        context = PersistentJSON("context.json", symphony_storage)
        with context as cache:
            assert cache["most_recent_date_seen"] == last_message_date_str


def test_save_doesnot_replace_existing_date(checkpoint, symphony_storage):
    last_message_date_str = "2023-04-27T11:34:56+00:00"
    most_recent_date_seen_str = "2023-04-27T11:45:32+00:00"

    # set the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        cache["most_recent_date_seen"] = most_recent_date_seen_str

    checkpoint.offset = isoparse(last_message_date_str)

    # assert the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        assert cache["most_recent_date_seen"] == most_recent_date_seen_str


def test_save_none_should_do_nothing(checkpoint, symphony_storage):
    last_message_date_str = None
    most_recent_date_seen_str = "2023-04-27T09:45:32+00:00"

    # set the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        cache["most_recent_date_seen"] = most_recent_date_seen_str

    checkpoint.offset = last_message_date_str

    # assert the cursor
    context = PersistentJSON("context.json", symphony_storage)
    with context as cache:
        assert cache["most_recent_date_seen"] == most_recent_date_seen_str
