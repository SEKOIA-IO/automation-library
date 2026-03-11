import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from office365.message_trace.trigger_office365_messagetrace_graph_api import Office365MessageTraceTriggerGraphAPI

LOGGER = logging.getLogger(__name__)


@pytest.fixture
def trigger(symphony_storage):
    trigger = Office365MessageTraceTriggerGraphAPI(data_path=symphony_storage)
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "tenant_id": "aa",
        "client_id": "aa",
        "client_secret": "aa",
        "intake_key": "aa",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }
    yield trigger


def test_fetch_events(trigger, requests_mock, message_trace_report_graph_api, start_time, end_time):
    with patch("office365.message_trace.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.acquire_token_silent = MagicMock()
        mock_msal.acquire_token_silent.return_value = {"access_token": "TOKEN"}

        trigger._get_access_token = Mock()
        requests_mock.get(
            "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces",
            json=message_trace_report_graph_api,
        )
        gen = trigger.fetch_events(start_time, end_time)
        for events in gen:
            assert type(events) is list


def test_fetch_events_wrong_json(trigger, requests_mock, message_trace_report, start_time, end_time):
    with patch("office365.message_trace.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.acquire_token_silent = MagicMock()
        mock_msal.acquire_token_silent.return_value = {"access_token": "TOKEN"}

        trigger._get_access_token = Mock()
        requests_mock.get(
            "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces",
            text="{}",
        )
        events = trigger.fetch_events(start_time, end_time)
        assert list(events) == []


def test_stepper_with_cursor(trigger, symphony_storage):
    date = datetime.now(timezone.utc)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("office365.message_trace.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == most_recent_date_requested


def test_stepper_with_cursor_older_than_30_days(trigger, symphony_storage):
    date = datetime.now(timezone.utc)
    most_recent_date_requested = date - timedelta(days=40)
    expected_date = date - timedelta(days=30)
    context = PersistentJSON("context.json", symphony_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("office365.message_trace.base.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start.replace(microsecond=0) == expected_date.replace(microsecond=0)


def test_stepper_without_cursor(trigger, symphony_storage):
    context = PersistentJSON("context.json", symphony_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_requested"] = None

    with patch("office365.message_trace.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == datetime(2023, 3, 22, 11, 55, 28, tzinfo=timezone.utc)
