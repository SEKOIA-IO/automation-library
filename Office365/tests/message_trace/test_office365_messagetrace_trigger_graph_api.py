import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

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
        "timedelta": 5,
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
