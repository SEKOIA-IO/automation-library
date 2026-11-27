import json
import logging
import os
from threading import Thread
from unittest.mock import Mock, patch

import pytest

from office365.message_trace.trigger_office365_messagetrace_oauth import Office365MessageTraceTrigger

LOGGER = logging.getLogger(__name__)
MODULE = "office365.message_trace.trigger_office365_messagetrace_oauth"


@pytest.fixture
def trigger(symphony_storage):
    trigger = Office365MessageTraceTrigger(data_path=symphony_storage)
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


def test_query_api_wrong_creds_403(trigger, requests_mock, message_trace_api_403, start_time, end_time):
    trigger._get_access_token = Mock()
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        json=message_trace_api_403,
        status_code=403,
    )
    assert trigger.query_api(start_time, end_time) == []
    assert "No permission to access the report for the organization" in trigger.log.call_args_list[1][1]["message"]


def test_query_api_wrong_creds_401(trigger, requests_mock, message_trace_api_401, start_time, end_time):
    trigger._get_access_token = Mock()
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        json=message_trace_api_401,
        status_code=401,
    )
    assert trigger.query_api(start_time, end_time) == []
    assert "Unauthorized: Access is denied due to invalid" in trigger.log.call_args_list[1][1]["message"]


def test_query_api(trigger, requests_mock, message_trace_report, start_time, end_time):
    trigger._get_access_token = Mock()
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        json=message_trace_report,
    )
    events = trigger.query_api(start_time, end_time)
    assert events == trigger.serialize_json(message_trace_report["d"]["results"])
    assert type(events) is list
    for event in events:
        assert type(event) is str
        assert type(json.loads(event)) is dict


def test_query_api_wrong_json(trigger, requests_mock, message_trace_report, start_time, end_time):
    trigger._get_access_token = Mock()
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        text="text",
    )
    events = trigger.query_api(start_time, end_time)
    assert events == []


def test_query_exception_api(trigger, requests_mock, message_trace_report, start_time, end_time):
    trigger._get_access_token = Mock()
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        [
            {"exc": Exception},
            {"json": message_trace_report},
        ],
    )
    events = trigger.query_api(start_time, end_time)
    assert events == trigger.serialize_json(message_trace_report["d"]["results"])
    assert type(events) is list
    for event in events:
        assert type(event) is str
        assert type(json.loads(event)) is dict


@pytest.mark.skipif("{'CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID'}.issubset(os.environ.keys()) == False")
def test_query_api_with_credentials(trigger, start_time, end_time):
    trigger.configuration = {
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "tenant_id": os.environ["TENANT_ID"],
        "intake_key": "aa",
        "frequency": 60,
    }
    events = trigger.query_api(start_time, end_time)
    assert len(events) != 0
    assert type(events) is list
    for event in events:
        assert type(event) is str
        assert type(json.loads(event)) is dict


@pytest.mark.real_sleep
@pytest.mark.skipif("{'CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID'}.issubset(os.environ.keys()) == False")
def test_trigger_with_credentials(trigger):
    trigger.push_events_to_intakes = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "frequency": 120,
        "timedelta": 5,
        "start_time": 3,
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "tenant_id": os.environ["TENANT_ID"],
        "intake_key": "aa",
    }

    thread = Thread(target=trigger.run, daemon=True)
    thread.start()
    thread.join(timeout=30)  # the trigger runs forever: wait 30 seconds for events

    # stop the trigger, so it doesn't keep querying Microsoft during the next tests
    trigger.stop()
    thread.join(timeout=5)

    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0


@pytest.mark.parametrize(
    "access_token,expected_headers",
    [
        pytest.param("TOKEN", {"Accept": "application/json", "Authorization": "Bearer TOKEN"}, id="token"),
        pytest.param(None, {}, id="no_token"),
    ],
)
def test_get_http_header(trigger, access_token, expected_headers):
    trigger._get_access_token = Mock(return_value=access_token)

    assert trigger._get_http_header() == expected_headers


def test_msal_app_is_cached_and_uses_tenant_authority(trigger):
    with patch(
        "office365.message_trace.trigger_office365_messagetrace_oauth.msal.ConfidentialClientApplication"
    ) as app:
        assert trigger._app is trigger._app

    app.assert_called_once_with("aa", authority="https://login.microsoftonline.com/aa", client_credential="aa")


@pytest.mark.parametrize(
    "silent_result,client_result,expected_token,expected_logs",
    [
        pytest.param({"access_token": "cached"}, None, "cached", 0, id="token_from_cache"),
        pytest.param(None, {"access_token": "fresh"}, "fresh", 0, id="token_from_client_credentials"),
        pytest.param(None, {"error": "invalid_client", "correlation_id": "42"}, None, 1, id="failure"),
    ],
)
def test_get_access_token(trigger, silent_result, client_result, expected_token, expected_logs):
    trigger._app = Mock()
    trigger._app.acquire_token_silent.return_value = silent_result
    trigger._app.acquire_token_for_client.return_value = client_result

    assert trigger._get_access_token() == expected_token
    assert trigger.log.call_count == expected_logs
    if expected_logs:
        trigger.log.assert_called_once_with(
            message=(
                "Failed to get an access token from Microsoft. "
                "Error: invalid_client - Description: None - Correlation ID: 42"
            ),
            level="error",
        )
