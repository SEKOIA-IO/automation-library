import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
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
        mock_msal.return_value.acquire_token_silent = MagicMock()
        mock_msal.return_value.acquire_token_silent.return_value = {"access_token": "TOKEN"}

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
        mock_msal.return_value.acquire_token_silent = MagicMock()
        mock_msal.return_value.acquire_token_silent.return_value = {"access_token": "TOKEN"}

        trigger._get_access_token = Mock()
        requests_mock.get(
            "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces",
            text="{}",
        )
        events = trigger.fetch_events(start_time, end_time)
        assert list(events) == []


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
    context = PersistentJSON("context.json", symphony_storage)

    fixed_now = datetime(2026, 3, 16, 1, 12, 00, tzinfo=UTC)
    most_recent_date_requested = fixed_now - timedelta(days=40)
    expected_date = fixed_now - timedelta(days=30)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("office365.message_trace.trigger_office365_messagetrace_graph_api.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
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


GRAPH_API_URL = "https://graph.microsoft.com/v1.0/admin/exchange/tracing/messageTraces"


@pytest.fixture
def mock_msal():
    with patch("office365.message_trace.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.return_value.acquire_token_silent.return_value = {"access_token": "TOKEN"}
        yield mock_msal


def test_events_cache_is_persisted_in_context(trigger, symphony_storage):
    trigger.events_cache["event-1"] = True
    trigger.events_cache["event-2"] = True

    trigger.save_events_cache()
    reloaded_cache = Office365MessageTraceTriggerGraphAPI(data_path=symphony_storage).load_events_cache()

    assert set(reloaded_cache.keys()) == {"event-1", "event-2"}


@pytest.mark.parametrize(
    "status_code,should_raise",
    [
        pytest.param(200, False, id="ok"),
        pytest.param(403, True, id="forbidden"),
        pytest.param(500, True, id="server_error"),
    ],
)
def test_handle_response_error(trigger, requests_mock, status_code, should_raise):
    requests_mock.get(GRAPH_API_URL, status_code=status_code, text="body" * 500)
    response = requests.get(GRAPH_API_URL, timeout=1)

    if should_raise:
        with pytest.raises(requests.HTTPError):
            trigger.handle_response_error(response)
        trigger.log.assert_called_once_with(
            message=f"Request on Microsoft Graph API failed with status {status_code} - {('body' * 500)[:500]}",
            level="error",
        )
    else:
        trigger.handle_response_error(response)
        trigger.log.assert_not_called()


@pytest.mark.parametrize(
    "pages,expected_pages",
    [
        pytest.param([{"value": [{"id": "1"}]}], [[{"id": "1"}]], id="single_page"),
        pytest.param(
            [
                {"value": [{"id": "1"}], "@odata.nextLink": f"{GRAPH_API_URL}?$skiptoken=page2"},
                {"value": [{"id": "2"}]},
            ],
            [[{"id": "1"}], [{"id": "2"}]],
            id="two_pages",
        ),
        pytest.param(
            [
                {"value": [{"id": "1"}], "@odata.nextLink": f"{GRAPH_API_URL}?$skiptoken=page2"},
                {"value": []},
            ],
            [[{"id": "1"}]],
            id="empty_last_page",
        ),
    ],
)
def test_fetch_events_pagination(trigger, requests_mock, mock_msal, start_time, end_time, pages, expected_pages):
    requests_mock.get(GRAPH_API_URL, [{"json": page} for page in pages])

    assert list(trigger.fetch_events(start_time, end_time)) == expected_pages
    assert requests_mock.call_count == len(pages)
    if len(pages) > 1:
        assert requests_mock.request_history[1].qs == {"$skiptoken": ["page2"]}


def test_fetch_events_does_nothing_when_stopped(trigger, requests_mock, start_time, end_time):
    trigger._stop_event.set()

    assert list(trigger.fetch_events(start_time, end_time)) == []
    assert requests_mock.call_count == 0
