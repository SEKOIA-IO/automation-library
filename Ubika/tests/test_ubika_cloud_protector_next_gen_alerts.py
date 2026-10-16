from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from respx import MockRouter

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_next_gen_alerts import (
    UbikaCloudProtectorNextGenAlertsConnector,
)
from ubika_modules.connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenAlertsConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = UbikaCloudProtectorNextGenBaseConnectorConfiguration(
        base_url="https://api.ubika.io/",
        namespace="sekoia",
        refresh_token="some_token_here",
        intake_key="intake_key",
        frequency=60,
        chunk_size=100,
        start_time=1,
    )
    yield trigger


@pytest.fixture
def message1():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {
            "items": [
                {
                    "logAlertUid": "098f6bcd4621d373cade4e832627b4f6",
                    "timestamp": "1747326567848",
                    "request": {"uid": "abcdef", "hostname": "ubika.integration.sekoia.cloud", "method": "GET"},
                    "context": {"assetName": "testAsset", "assetNamespace": "sekoia", "reaction": "BLOCKED"},
                }
            ],
            "nextPageToken": "token123",
        },
    }


@pytest.fixture
def message2():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {"items": [], "nextPageToken": "tokenEnd"},
    }


def test_get_event_id(trigger):
    assert trigger.get_event_id({"logAlertUid": "abc"}) == "abc"
    assert trigger.get_event_id({}) is None


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_get_pages_with_pagination(respx_mock: MockRouter, trigger, message1, message2):
    respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
    )

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={"filters.fromDate": "1747326567845", "pagination.realtime": True, "pagination.pageSize": 100},
    ).mock(return_value=httpx.Response(200, json=message1))

    respx_mock.get(
        f"{trigger.configuration.base_url}rest/logs.ubika.io/v1/ns/sekoia/security-events",
        params={"pagination.pageToken": "token123", "pagination.pageSize": 100, "pagination.realtime": True},
    ).mock(return_value=httpx.Response(200, json=message2))

    events = trigger._get_pages(
        endpoint="security-events",
        params={"filters.fromDate": 1747326567845, "pagination.realtime": True, "pagination.pageSize": 100},
    )

    assert list(events) == [message1["spec"]["items"]]


def test_fetch_events_tracks_checkpoint(trigger):
    """fetch_events yields new events and persists max timestamp + 1ms as checkpoint."""
    from_ms = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    event_ms = from_ms + 5000
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = from_ms
    page = [{"logAlertUid": "a", "timestamp": str(event_ms)}]
    trigger._get_pages = MagicMock(return_value=[page])

    events = list(trigger.fetch_events())

    assert events == [page]
    with trigger.context as cache:
        assert cache["most_recent_timestamp_seen"] == event_ms + 1


def test_fetch_events_persists_intermediate_checkpoint(trigger):
    """A raw checkpoint is persisted per page so a restart replays at most one page."""
    from_ms = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    p1 = [{"logAlertUid": "a", "timestamp": str(from_ms + 1000)}]
    p2 = [{"logAlertUid": "b", "timestamp": str(from_ms + 2000)}]
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = from_ms
    trigger._get_pages = MagicMock(return_value=iter([p1, p2]))

    gen = trigger.fetch_events()

    assert next(gen) == p1
    assert next(gen) == p2
    # after resuming past p1's yield, the raw p1 maximum is persisted (no +1)
    with trigger.context as cache:
        assert cache["most_recent_timestamp_seen"] == from_ms + 1000

    # draining persists p2's maximum + 1ms as the final checkpoint
    list(gen)
    with trigger.context as cache:
        assert cache["most_recent_timestamp_seen"] == from_ms + 2000 + 1


def test_fetch_events_deduplicates_across_calls(trigger, message1):
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = 1747326567845
    trigger._get_pages = MagicMock(return_value=[message1["spec"]["items"]])

    first = list(trigger.fetch_events())
    assert first == [message1["spec"]["items"]]

    # Second call returns the same page: everything is filtered out by the cache
    trigger._get_pages = MagicMock(return_value=[message1["spec"]["items"]])
    second = list(trigger.fetch_events())
    assert second == []


def test_next_batch_pushes_events(trigger, message1):
    trigger.fetch_events = MagicMock(return_value=[message1["spec"]["items"]])

    trigger.next_batch()

    trigger.push_events_to_intakes.assert_called_once()
    pushed = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed) == 1


def test_run_logs_and_continues_on_exception(trigger):
    """A failing batch must be logged and retried, not stop the connector."""
    calls = []

    def side_effect():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        trigger._stop_event.set()

    trigger.next_batch = MagicMock(side_effect=side_effect)

    trigger.run()

    assert len(calls) == 2  # retried after the exception
    trigger.log_exception.assert_called_once()
    assert trigger.log_exception.call_args.kwargs["message"] == "Failed to fetch events"


def test_run_closes_and_resets_client(trigger):
    trigger._stop_event.set()
    mock_client = MagicMock()
    trigger._client = mock_client

    trigger.run()

    mock_client.close.assert_called_once()
    assert trigger._client is None
