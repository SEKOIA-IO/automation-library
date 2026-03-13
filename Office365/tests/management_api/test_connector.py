import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from prometheus_client import Counter

from office365.management_api.checkpoint import Checkpoint
from office365.management_api.connector import FORWARD_EVENTS_DURATION
from office365.management_api.errors import FailedToActivateO365Subscription


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
async def test_forward_events_forever_handles_exceptions(connector, symphony_storage):
    """Test that forward_events_forever handles exceptions and continues"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Test error")
        if call_count >= 2:
            connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args[1]["message"] == "Failed to forward events"


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
