import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from respx import MockRouter

from ubika_modules import UbikaModule
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
    trigger.configuration = {
        "namespace": "sekoia",
        "refresh_token": "some_token_here",
        "intake_key": "intake_key",
        "chunk_size": 100,
    }
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
    with patch("ubika_modules.connector_ubika_cloud_protector_base.time") as mock_time:
        mock_time.sleep = MagicMock()

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
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
            params={
                "filters.fromDate": "1747326567845",
                "pagination.pageSize": "100",
            },
        ).mock(return_value=httpx.Response(200, json=message1))

        respx_mock.get(
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/traffic-logs",
            params={
                "pagination.pageToken": "token123",
                "pagination.pageSize": "100",
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


def test_process_batch(trigger):
    # Stub 2 pages
    pages = [
        [{"timestamp": "100"}, {"timestamp": "200"}],
        [{"timestamp": "150"}, {"timestamp": "250"}],
    ]
    trigger._get_pages = MagicMock(return_value=pages)

    new_ts = trigger.process_batch(start_ts=50)

    # Verify it pushed both pages
    assert trigger.push_events_to_intakes.call_count == 2
    # Verify returned timestamp is the max seen = 250
    assert new_ts == 250


def test_run_calls_process_batch_and_updates_checkpoint(trigger, monkeypatch, data_storage):
    """
    Ensure run():
     - reads the existing checkpoint from context.json
     - calls process_batch(start_ts) exactly once
     - writes the returned value back to context.json
     - stops when _stop_event.is_set() becomes True
    """
    # Pre‐seed the context with a known checkpoint
    initial_ts = 1234
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = initial_ts

    # Stub out process_batch to return a new checkpoint
    new_ts = 5678
    trigger.process_batch = MagicMock(return_value=new_ts)

    # Ensure run only loops once: first False, then True
    trigger._stop_event.is_set = MagicMock(side_effect=[False, True])

    # 4) Avoid real sleeping
    monkeypatch.setattr(time, "sleep", lambda s: None)

    # Call run()
    trigger.run()

    # Verify process_batch was invoked with the initial timestamp
    trigger.process_batch.assert_called_once_with(start_ts=initial_ts)

    # Verify context.json was updated to new_ts
    with trigger.context as cache:
        assert cache["most_recent_timestamp_seen"] == new_ts
