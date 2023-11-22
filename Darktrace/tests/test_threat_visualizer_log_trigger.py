import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from darktrace_modules import DarktraceModule, Endpoints
from darktrace_modules.threat_visualizer_log_trigger import (
    ThreatVisualizerLogConnector,
    ThreatVisualizerLogConsumer,
)


@pytest.fixture
def trigger(symphony_storage):
    module = DarktraceModule()
    trigger = ThreatVisualizerLogConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "api_url": "https://api_url",
        "private_key": "private",
        "public_key": "public",
    }
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


def get_json(filename):
    with open(filename, "r") as file:
        return json.load(file)


@pytest.fixture
def modelbreaches_response():
    return get_json("tests/modelbreaches_response.txt")


@pytest.fixture
def aianalyst_response():
    return get_json("tests/aianalyst_response.txt")


def test_modelbreaches_consumer(trigger, modelbreaches_response):
    with patch(
        "darktrace_modules.threat_visualizer_log_trigger.time"
    ) as mock_time, requests_mock.Mocker() as mock_request:
        last_ts = 1687774141.000
        batch_start = 1687774141.000
        batch_end = 1688465633.434
        mock_request.get(
            trigger.module.configuration.api_url
            + "/modelbreaches?starttime=1687774141000&includeallpinned=False&historicmodelonly=false",
            json=modelbreaches_response,
        )

        mock_time.time.side_effect = [batch_start, last_ts, last_ts, batch_end]

        connector = trigger
        ThreatVisualizerLogConsumer(connector=connector, endpoint=Endpoints.MODEL_BREACHES).next_batch()

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 1
        assert trigger.push_events_to_intakes.call_count == 1


def test_aianalyst_consumer(trigger, aianalyst_response):
    with patch(
        "darktrace_modules.threat_visualizer_log_trigger.time"
    ) as mock_time, requests_mock.Mocker() as mock_request:
        last_ts = 1687774141.000
        batch_start = 1687774141.000
        batch_end = 1688465633.434
        mock_request.get(
            trigger.module.configuration.api_url
            + "/aianalyst/incidentevents?starttime=1687774141000&includeallpinned=false&historicmodelonly=false",
            json=aianalyst_response,
        )

        mock_time.time.side_effect = [batch_start, last_ts, last_ts, batch_end]

        ThreatVisualizerLogConsumer(connector=trigger, endpoint=Endpoints.AI_ANALYST).next_batch()

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 16
        assert trigger.push_events_to_intakes.call_count == 1


def test_start_consumers(trigger):
    with patch("darktrace_modules.threat_visualizer_log_trigger.ThreatVisualizerLogConsumer.start") as mock_start:
        consumers = trigger.start_consumers()

        assert consumers is not None

        assert Endpoints.AI_ANALYST in consumers
        assert Endpoints.MODEL_BREACHES in consumers

        assert mock_start.called


def test_stop_consumers(trigger):
    consumers = {
        Endpoints.MODEL_BREACHES: Mock(**{"is_alive.return_value": False}),
        Endpoints.AI_ANALYST: Mock(**{"is_alive.return_value": True}),
    }

    trigger.stop_consumers(consumers)

    offline_consumer = consumers.get(Endpoints.AI_ANALYST)
    assert offline_consumer is not None
    assert offline_consumer.stop.called


def test_supervise_consumers(trigger):
    with patch("darktrace_modules.threat_visualizer_log_trigger.ThreatVisualizerLogConsumer.start") as mock_start:
        consumers = {
            Endpoints.MODEL_BREACHES: Mock(**{"is_alive.return_value": False}),
            Endpoints.AI_ANALYST: Mock(**{"is_alive.return_value": True}),
        }

        trigger.supervise_consumers(consumers)
        assert mock_start.call_count == 1
