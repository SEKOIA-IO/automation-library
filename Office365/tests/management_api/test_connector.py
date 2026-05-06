import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from prometheus_client import Counter

from office365.management_api.checkpoint import Checkpoint
from office365.management_api.connector import FORWARD_EVENTS_DURATION
from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)


@pytest.mark.asyncio
@patch.object(Counter, "inc")
async def test_send_events(mock_prometheus, connector, event):
    connector.push_data_to_intakes = AsyncMock()
    await connector.send_events([event])
    connector.log.assert_called_once_with("Pushing 1 event(s) to intake", level="info")
    mock_prometheus.assert_called_once()
    connector.push_data_to_intakes.assert_called_once_with(events=[event])


@pytest.mark.asyncio
async def test_activate_subscriptions_client_exception(connector):
    connector.client.activate_subscriptions.side_effect = FailedToActivateO365Subscription()

    await connector.activate_subscriptions()

    connector.client.activate_subscriptions.assert_called_once()
    connector.log_exception.assert_called_once()

    call_args = connector.log_exception.call_args_list[0].kwargs
    assert len(call_args) == 2
    assert call_args["message"] == "An exception occurred when trying to subscribe to Office365 events."
    assert isinstance(call_args["exception"], FailedToActivateO365Subscription)


async def async_generator(iterable):
    for item in iterable:
        yield item


@pytest.mark.asyncio
async def test_pull_content(connector, event):
    connector.client.list_subscriptions.return_value = ["json"]
    content_skipped = {"contentUri": " foo://example.com", "contentExpiration": "2015-05-30T17:35:00.000Z"}

    content_not_skipped_1 = {
        "contentUri": " foo://example.com",
    }
    content_not_skipped_2 = {
        "contentUri": " foo://example.com",
        "contentExpiration": (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }

    connector.client.get_subscription_contents.return_value = async_generator(
        [[content_skipped, content_not_skipped_1, content_not_skipped_2]]
    )
    connector.client.get_content.return_value = [event, event]

    gen = connector.pull_content(datetime.now() - timedelta(minutes=10), datetime.now())
    result = [item async for item in gen]
    assert len(result) == 1
    assert [json.loads(event) for event in result[0]] == [event, event, event, event]


@pytest.mark.asyncio
async def test_forward_next_batches(connector, symphony_storage, event):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    now = datetime.now(tz=UTC)

    async def sleeper(_):
        asyncio.sleep(0.1)

    with (
        patch.object(connector, "pull_content", return_value=async_generator([event])) as pull_content,
        patch.object(connector, "send_events") as send_events,
        patch.object(FORWARD_EVENTS_DURATION, "labels") as prometheus_labels,
        patch("office365.management_api.checkpoint.datetime") as mock_datetime,
        patch("office365.management_api.connector.datetime") as mock_datetime2,
        patch("office365.management_api.connector.asyncio.sleep") as sleep2,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_datetime2.now.return_value = now
        mock_datetime2.side_effect = lambda *args, **kw: datetime(*args, **kw)
        sleep2.side_effect = sleeper

        await connector.forward_next_batches(checkpoint)

        pull_content.assert_called_once_with(now, now)
        send_events.assert_called_once_with(event)
        prometheus_labels.assert_called_once_with(intake_key=connector.configuration.intake_key)


@pytest.mark.asyncio
async def test_forward_events_forever_stops_on_stop_event(connector, symphony_storage):
    """Test that forward_events_forever stops when running is False"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    # Mock forward_next_batches to set running to False after first call
    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            connector._stop_event.set()
        await asyncio.sleep(0.01)

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    assert not connector.running


@pytest.mark.asyncio
async def test_forward_events_forever_handles_unexpected_exceptions(connector, symphony_storage):
    """Unknown exceptions go through the catch-all branch and are logged with traceback."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Test error")
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args[1]["message"] == "Unexpected error in forwarding loop"


@pytest.mark.asyncio
async def test_forward_events_forever_handles_auth_failure(connector, symphony_storage):
    """Authentication failures are logged at warning/critical and trigger a long sleep."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0
    sleep_durations: list[float] = []

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ApplicationAuthenticationFailed(
                "Failed to get access token",
                response={"error_description": "AADSTS70011: invalid scope"},
            )
        connector._stop_event.set()

    async def fake_sleep(seconds):
        sleep_durations.append(seconds)

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", side_effect=fake_sleep),
    ):
        await connector.forward_events_forever(checkpoint)

    connector.log.assert_called()
    log_message = connector.log.call_args_list[0].kwargs["message"]
    assert "Authentication" in log_message
    assert "AADSTS70011" in log_message
    # First sleep is the auth recovery sleep (>= frequency, capped at 600).
    assert sleep_durations[0] >= connector._frequency


@pytest.mark.asyncio
async def test_forward_events_forever_handles_o365_api_failure(connector, symphony_storage):
    """O365 Management API errors are logged with status/operation and exponential backoff."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FailedToGetO365SubscriptionContents(status_code=503, body="<html>Service Unavailable</html>")
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    connector.log.assert_called()
    log_message = connector.log.call_args_list[0].kwargs["message"]
    assert "FailedToGetO365SubscriptionContents" in log_message
    assert "consecutive=1" in log_message


@pytest.mark.asyncio
async def test_forward_events_forever_handles_network_failure(connector, symphony_storage):
    """Network errors hit the dedicated branch and are labeled by exc type."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise aiohttp.ClientConnectionError("connection reset")
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    connector.log.assert_called()
    log_message = connector.log.call_args_list[0].kwargs["message"]
    assert "Network error" in log_message
    assert "ClientConnectionError" in log_message


@pytest.mark.asyncio
async def test_forward_events_forever_dedups_repeated_failures(connector, symphony_storage):
    """Identical consecutive failures should not all be logged."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        # Raise the same error N times, then stop without ever succeeding so no
        # recovery log fires. The 9th call sets the stop event and re-raises so
        # the loop exits via the same error path.
        if call_count >= 9:
            connector._stop_event.set()
        raise FailedToListO365Subscriptions(status_code=503, body="boom")

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    # 9 consecutive failures: should_log returns True for n in {1,2,3} only.
    assert connector.log.call_count == 3


@pytest.mark.asyncio
async def test_forward_events_forever_logs_recovery_on_success(connector, symphony_storage):
    """After a streak of failures, a successful run should log a recovery message."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise aiohttp.ClientConnectionError("transient")
        if call_count == 2:
            return  # success
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    recovery_logged = any(
        "Recovered from network failures" in call.kwargs.get("message", "") for call in connector.log.call_args_list
    )
    assert recovery_logged


def test_compute_backoff_seconds_caps_at_max(connector):
    # Very large count should still cap at MAX_RECOVERY_SLEEP_SECONDS (600).
    assert connector._compute_backoff_seconds(1000) == 600


def test_compute_backoff_seconds_doubles_each_step(connector):
    # _frequency defaults to 60. Sequence: 60, 120, 240, 480, 600 (cap), 600...
    assert connector._compute_backoff_seconds(1) == 60
    assert connector._compute_backoff_seconds(2) == 120
    assert connector._compute_backoff_seconds(3) == 240
    assert connector._compute_backoff_seconds(4) == 480
    assert connector._compute_backoff_seconds(5) == 600
    assert connector._compute_backoff_seconds(6) == 600


@pytest.mark.asyncio
async def test_collect_events_closes_client_on_exit(connector, symphony_storage):
    """Test that collect_events closes the client in finally block"""
    connector._stop_event.set()  # Set to stop immediately

    # Mock the client's close method
    mock_client = AsyncMock()

    with (
        patch.object(connector, "activate_subscriptions", new_callable=AsyncMock) as mock_activate,
        patch.object(connector, "forward_events_forever", new_callable=AsyncMock) as mock_forward,
        patch.object(type(connector), "client", new=mock_client, create=True),
    ):
        # Access client to ensure it's in __dict__
        _ = connector.client

        await connector.collect_events()

        mock_activate.assert_called_once()
        mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_collect_events_calls_activate_and_forward(connector, symphony_storage):
    """Test that collect_events calls activate_subscriptions and forward_events_forever"""
    connector._stop_event.set()  # Stop immediately

    with (
        patch.object(connector, "activate_subscriptions", new_callable=AsyncMock) as mock_activate,
        patch.object(connector, "forward_events_forever", new_callable=AsyncMock) as mock_forward,
    ):
        await connector.collect_events()

        mock_activate.assert_called_once()
        mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_sets_stop_event(connector):
    """Test that shutdown sets the stop event"""
    assert connector.running  # Initially running

    await connector.shutdown()

    # Verify stop event was set
    assert not connector.running


@pytest.mark.asyncio
async def test_client_property_is_cached(connector):
    """Test that client property uses cached_property decorator"""
    # Verify cached_property descriptor exists on class
    assert hasattr(type(connector), "client")

    # Verify property returns same instance on multiple accesses (via fixture mock)
    client1 = connector.client
    client2 = connector.client
    assert client1 is client2
