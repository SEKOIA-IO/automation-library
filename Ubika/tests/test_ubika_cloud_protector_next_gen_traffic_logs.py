from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from respx import MockRouter

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)
from ubika_modules.connector_ubika_cloud_protector_next_gen_traffic_logs import (
    UbikaCloudProtectorNextGenTrafficLogsConnector,
)


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenTrafficLogsConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = UbikaCloudProtectorNextGenBaseConnectorConfiguration(
        base_url="https://api.ubika.io/",
        namespace="sekoia",
        refresh_token="some_token_here",
        intake_key="intake_key",
        chunk_size=100,
        frequency=60,
        start_time=1,
    )
    yield trigger


@pytest.fixture
def message1():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "TrafficLogs",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {
            "items": [
                {
                    "timestamp": "1777383278301",
                    "context": {"assetName": "testAsset", "assetNamespace": "example", "reaction": "BLOCKED"},
                    "request": {"uid": "uid-1", "hostname": "example.com", "method": "GET", "path": "/.aws/credentials"},
                    "response": {"statusCode": 403},
                },
                {
                    "timestamp": "1777383263946",
                    "context": {"assetName": "testAsset", "assetNamespace": "example", "reaction": "PASSED"},
                    "request": {"uid": "uid-2", "hostname": "example.com", "method": "GET", "path": "/"},
                    "response": {"statusCode": 403},
                },
            ],
            "nextPageToken": "token123",
        },
    }


@pytest.fixture
def message2():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "TrafficLogs",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {"items": [], "nextPageToken": "tokenEnd"},
    }


def test_get_event_id(trigger):
    assert trigger.get_event_id({"request": {"uid": "uid-1"}}) == "uid-1"
    assert trigger.get_event_id({"request": {}}) is None
    assert trigger.get_event_id({}) is None


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_get_pages(respx_mock: MockRouter, trigger, message1, message2):
    respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
    )

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
        params={"filters.fromDate": "1747326567845", "pagination.pageSize": 100, "pagination.realtime": True},
    ).mock(return_value=httpx.Response(200, json=message1))

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
        params={"pagination.pageToken": "token123", "pagination.pageSize": 100, "pagination.realtime": True},
    ).mock(return_value=httpx.Response(200, json=message2))

    events = trigger._get_pages(
        endpoint="traffic-logs",
        params={"filters.fromDate": 1747326567845, "pagination.pageSize": 100, "pagination.realtime": True},
    )

    assert list(events) == [message1["spec"]["items"]]


def test_fetch_events_tracks_checkpoint(trigger):
    """fetch_events persists the greatest timestamp seen + 1ms."""
    from_ms = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    event_ms = from_ms + 5000
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = from_ms
    page = [
        {"timestamp": str(event_ms), "request": {"uid": "uid-1"}},
        {"timestamp": str(event_ms - 1000), "request": {"uid": "uid-2"}},
    ]
    trigger._get_pages = MagicMock(return_value=[page])

    events = list(trigger.fetch_events())

    assert events == [page]
    with trigger.context as cache:
        assert cache["most_recent_timestamp_seen"] == event_ms + 1


def test_fetch_events_forwards_events_without_id(trigger):
    """Events missing request.uid are forwarded but not deduplicated."""
    pages = [
        [
            {"timestamp": "100", "request": {"uid": "uid-100"}},
            {"timestamp": "200"},
            {"timestamp": "200"},
        ]
    ]
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = 50
    trigger._get_pages = MagicMock(return_value=pages)

    events = list(trigger.fetch_events())

    assert len(events[0]) == 3


def test_next_batch_pushes_events(trigger, message1):
    trigger.fetch_events = MagicMock(return_value=[message1["spec"]["items"]])

    trigger.next_batch()

    trigger.push_events_to_intakes.assert_called_once()
    pushed = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed) == 2


def test_run_logs_and_continues_on_exception(trigger):
    calls = []

    def side_effect():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        trigger._stop_event.set()

    trigger.next_batch = MagicMock(side_effect=side_effect)

    trigger.run()

    assert len(calls) == 2
    trigger.log_exception.assert_called_once()
    assert trigger.log_exception.call_args.kwargs["message"] == "Failed to fetch events"
