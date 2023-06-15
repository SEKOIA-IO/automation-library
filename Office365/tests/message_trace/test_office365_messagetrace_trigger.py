import json
import logging
import os
import time
from threading import Thread
from unittest.mock import Mock

import pytest

from office365.message_trace.trigger_office365_messagetrace import (
    Office365MessageTraceTrigger,
)

LOGGER = logging.getLogger(__name__)


@pytest.fixture
def trigger(symphony_storage):
    trigger = Office365MessageTraceTrigger(data_path=symphony_storage)
    trigger.log = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "account_name": "aa",
        "account_password": "aa",
        "intake_key": "aa",
        "frequency": 60,
    }
    trigger.push_events_to_intakes = Mock()
    yield trigger


def test_query_api_wrong_creds(trigger, requests_mock, message_trace_api_401, start_time, end_time):
    requests_mock.get(
        "https://reports.office365.com/ecp/reportingwebservice/reporting.svc/MessageTrace?$format=json",
        json=message_trace_api_401,
        status_code=401,
    )
    assert trigger.query_api(start_time, end_time) == []
    assert "Unauthorized: Access is denied due to invalid credentials." in trigger.log.call_args_list[1][1]["message"]


def test_query_api(trigger, requests_mock, message_trace_report, start_time, end_time):
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


@pytest.mark.skipif("{'O365_EMAIL', 'O365_PASSWORD'}.issubset(os.environ.keys()) == False")
def test_query_api_with_credentials(trigger, start_time, end_time):
    trigger.configuration = {
        "account_name": os.environ["O365_EMAIL"],
        "account_password": os.environ["O365_PASSWORD"],
        "intake_key": "aa",
        "frequency": 60,
    }
    events = trigger.query_api(start_time, end_time)
    assert len(events) != 0
    assert type(events) is list
    for event in events:
        assert type(event) is str
        assert type(json.loads(event)) is dict


@pytest.mark.skipif("{'O365_EMAIL', 'O365_PASSWORD'}.issubset(os.environ.keys()) == False")
def test_trigger_with_credentials(trigger):
    trigger.log = Mock()
    trigger.module.configuration = {}
    trigger.configuration = {
        "frequency": 120,
        "timedelta": 5,
        "start_time": 3,
        "account_name": os.environ["O365_EMAIL"],
        "account_password": os.environ["O365_PASSWORD"],
        "intake_key": "",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    thread = Thread(target=trigger.run)
    thread.start()
    time.sleep(30)
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(calls) > 0
