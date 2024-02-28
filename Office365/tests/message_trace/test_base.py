from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from office365.message_trace.base import Office365MessageTraceBaseTrigger


class TestTrigger(Office365MessageTraceBaseTrigger):
    def query_api(self, start: datetime, end: datetime):
        return


@pytest.fixture
def trigger(symphony_storage):
    trigger = TestTrigger(data_path=symphony_storage)
    trigger.log = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "account_name": "aa",
        "account_password": "aa",
        "intake_key": "aa",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }
    trigger.push_events_to_intakes = Mock()
    yield trigger


def test_stepper_with_cursor(trigger, symphony_storage):
    date = datetime.now(UTC)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("office365.message_trace.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == most_recent_date_requested


def test_stepper_with_cursor_older_than_30_days(trigger, symphony_storage):
    date = datetime.now(UTC)
    most_recent_date_requested = date - timedelta(days=40)
    expected_date = date - timedelta(days=30)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("office365.message_trace.base.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start.replace(microsecond=0) == expected_date.replace(microsecond=0)


def test_stepper_without_cursor(trigger, symphony_storage):
    context = PersistentJSON("context.json", symphony_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_requested"] = None

    with patch("office365.message_trace.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == datetime(2023, 3, 22, 11, 55, 28, tzinfo=UTC)
