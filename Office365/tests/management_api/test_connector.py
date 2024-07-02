import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
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
    connector.client.get_subscription_contents.return_value = async_generator([[{"contentUri": " foo://example.com"}]])
    connector.client.get_content.return_value = [event, event]

    gen = connector.pull_content(datetime.now() - timedelta(minutes=10), datetime.now())
    result = [item async for item in gen]
    assert len(result) == 1
    assert [json.loads(event) for event in result[0]] == [event, event]


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
