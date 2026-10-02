from datetime import UTC, datetime
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
        timedelta=5,
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
                    "request": {
                        "uid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "hostname": "example.comm",
                        "method": "GET",
                        "path": "/.aws/credentials",
                        "headers": [
                            {"key": "referer", "value": "-"},
                            {"key": "user-agent", "value": "Googlebot-News"},
                        ],
                        "ipSource": "192.0.2.1",
                        "query": "",
                        "size": "292",
                    },
                    "response": {
                        "backendResponseTime": "0",
                        "backendStatusCode": 0,
                        "size": "520",
                        "statusCode": 403,
                        "totalResponseTime": "1589",
                    },
                },
                {
                    "timestamp": "1777383263946",
                    "context": {"assetName": "testAsset", "assetNamespace": "example", "reaction": "PASSED"},
                    "request": {
                        "uid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "hostname": "example.com",
                        "method": "GET",
                        "path": "/",
                        "headers": [
                            {
                                "key": "user-agent",
                                "value": "Opera/9.80 (X11; Linux i686; U; en) Presto/2.2.15 Version/10.10",
                            },
                            {"key": "referer", "value": "-"},
                        ],
                        "ipSource": "192.0.2.17",
                        "query": "",
                        "size": "332",
                    },
                    "response": {
                        "backendResponseTime": "0",
                        "backendStatusCode": 0,
                        "size": "522",
                        "statusCode": 403,
                        "totalResponseTime": "1861",
                    },
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


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_get_pages(respx_mock: MockRouter, trigger, message1, message2):
    respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
    )

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
        params={
            "filters.fromDate": "1747326567845",
            "pagination.pageSize": 100,
        },
    ).mock(return_value=httpx.Response(200, json=message1))

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
        params={
            "pagination.pageToken": "token123",
            "pagination.pageSize": 100,
            "pagination.realtime": True,
        },
    ).mock(return_value=httpx.Response(200, json=message2))

    trigger.from_timestamp = 1747326567845
    events = trigger._get_pages(
        endpoint="traffic-logs",
        params={
            "filters.fromDate": 1747326567845,
            "pagination.pageSize": 100,
        },
    )

    assert list(events) == [message1["spec"]["items"]]


def test_next_batch(trigger):
    """
    Test that next_batch() fetches pages, serializes events, and pushes them to intakes.
    """
    # Stub 2 pages of events
    pages = [
        [
            {"timestamp": 100, "request": {"uid": "uid-100"}},
            {"timestamp": 200, "request": {"uid": "uid-200"}},
        ],
        [
            {"timestamp": 150, "request": {"uid": "uid-150"}},
            {"timestamp": 250, "request": {"uid": "uid-250"}},
        ],
    ]
    trigger._get_pages = MagicMock(return_value=pages)

    # Call next_batch with a time range
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)

    trigger.next_batch(start=start, end=end)

    # Verify it pushed both pages (2 calls, once per page)
    assert trigger.push_events_to_intakes.call_count == 2

    # Verify the context was updated with the end time
    with trigger.context as cache:
        assert cache["most_recent_date_seen"] == end.isoformat()


def test_next_batch_keeps_processing_corrupted_events_without_id(trigger):
    """
    Events missing request.uid are forwarded but not deduplicated.
    """
    pages = [
        [
            {"timestamp": 100, "request": {"uid": "uid-100"}},
            {"timestamp": 200},
            {"timestamp": 200},
        ]
    ]
    trigger._get_pages = MagicMock(return_value=pages)

    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)
    trigger.next_batch(start=start, end=end)

    trigger.push_events_to_intakes.assert_called_once()
    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed_events) == 3


def test_run_calls_next_batch_and_updates_checkpoint(trigger, monkeypatch):
    """
    Ensure run():
     - uses stepper.ranges() to generate time windows
     - calls next_batch() for each window
     - writes the end time to context.json
     - stops when _stop_event.is_set() becomes True
    """
    # Create mock time ranges
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)
    ranges = [(start, end)]

    # Mock the stepper to return our controlled ranges
    mock_stepper = MagicMock()
    mock_stepper.ranges.return_value = iter(ranges)  # Use iter() to create a generator
    monkeypatch.setattr(trigger, "stepper", mock_stepper)

    # Mock _stop_event.is_set() to return False to allow processing
    trigger._stop_event.is_set = MagicMock(return_value=False)

    # Mock _get_pages to return an empty list (no events)
    trigger._get_pages = MagicMock(return_value=[])

    # Call run()
    trigger.run()

    # Verify context.json was updated with the end time
    with trigger.context as cache:
        assert cache.get("most_recent_date_seen") == end.isoformat()


def test_run_logs_exception_on_process_error(trigger, monkeypatch):
    """
    If next_batch raises an exception, run() should catch it,
    call log_exception(e, message="Failed to fetch events"),
    then break and stop the connector.
    """
    # Create mock time ranges
    start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)
    ranges = [(start, end)]

    # Mock the stepper
    mock_stepper = MagicMock()
    mock_stepper.ranges.return_value = iter(ranges)  # Use iter() to create a generator
    monkeypatch.setattr(trigger, "stepper", mock_stepper)

    # Stub next_batch to throw
    exc = RuntimeError("oops")
    trigger.next_batch = MagicMock(side_effect=exc)

    # Spy on log_exception
    trigger.log_exception = MagicMock()

    # Call run()
    trigger.run()

    # Verify next_batch was called
    trigger.next_batch.assert_called_once_with(start, end)

    # Verify log_exception was called with the error and message
    trigger.log_exception.assert_called_once()
    args = trigger.log_exception.call_args
    assert args.kwargs["message"] == "Failed to fetch events"

    # Assert we caught & logged the exception
    trigger.log_exception.assert_called_once_with(exc, message="Failed to fetch events")
