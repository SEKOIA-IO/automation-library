import asyncio
import gzip
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from google.cloud.pubsub_v1.subscriber.message import Message
from google.cloud.pubsublite.types import CloudRegion, CloudZone
from pytest import fixture

from netskope_modules.connectors.connector_pubsub_lite import PubSubLite


class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


@fixture
def trigger(credentials, symphony_storage):
    trigger = PubSubLite(data_path=symphony_storage)
    trigger.configuration = {
        "project_id": "project_id",
        "subject_id": "subject_id",
        "cloud_region": "cloud_region",
        "intake_key": "intake_key",
        "subscription_id": "subscription_id",
        "credentials": credentials,
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_data_to_intakes = AsyncMock()
    yield trigger


def create_async_message(data: bytes, dt: datetime) -> Message:
    message = Mock()
    message.data = data
    message.publish_time = dt

    return message


def test_configuration(trigger):
    trigger.set_credentials()
    assert trigger.CREDENTIALS_PATH.exists()


def test_execute_calls_set_credentials_and_super_execute(trigger):
    with (
        patch.object(PubSubLite, "set_credentials") as mock_set_credentials,
        patch("sekoia_automation.aio.connector.AsyncConnector.execute") as mock_super_execute,
    ):
        trigger.execute()

    mock_set_credentials.assert_called_once()
    mock_super_execute.assert_called_once()


def test_load_checkpoint_updates_last_seen_timestamp(trigger):
    expected_ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc).timestamp()
    with trigger.context as cache:
        cache["last_timestamp"] = expected_ts

    asyncio.run(trigger.load_checkpoint())

    assert abs(trigger.last_seen_timestamp.timestamp() - expected_ts) < 1


def test_load_checkpoint_without_cache_keeps_existing_timestamp(trigger):
    baseline = trigger.last_seen_timestamp
    with trigger.context as cache:
        cache.pop("last_timestamp", None)

    asyncio.run(trigger.load_checkpoint())

    assert trigger.last_seen_timestamp == baseline


def test_save_checkpoint_persists_last_seen_timestamp(trigger):
    trigger.last_seen_timestamp = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)

    asyncio.run(trigger.save_checkpoint())

    with trigger.context as cache:
        cached = cache.get("last_timestamp")

    assert cached == trigger.last_seen_timestamp.timestamp()


def test_stop_logs_and_calls_super_stop(trigger):
    with patch("sekoia_automation.aio.connector.AsyncConnector.stop") as mock_super_stop:
        trigger.stop()

    trigger.log.assert_called_once_with(message="Stopping Google Cloud PubSub connector", level="info")
    mock_super_stop.assert_called_once()


def test_location_returns_cloud_region_when_zone_is_absent(trigger):
    trigger.configuration.zone_id = None
    trigger.__dict__.pop("location", None)

    location = trigger.location

    assert isinstance(location, CloudRegion)


def test_location_returns_cloud_zone_when_zone_is_present(trigger):
    trigger.configuration.zone_id = "a"
    trigger.__dict__.pop("location", None)

    location = trigger.location

    assert isinstance(location, CloudZone)


def test_subscription_path_uses_credentials_location_and_subscription(trigger):
    trigger.configuration.zone_id = None
    trigger.__dict__.pop("location", None)
    trigger.__dict__.pop("subscription_path", None)

    path = trigger.subscription_path

    assert path.project == trigger.configuration.credentials["project_id"]
    assert path.name == trigger.configuration.subscription_id


@pytest.mark.parametrize(
    "content,expected",
    [
        (gzip.compress(b"hello"), True),
        (b"hello", False),
    ],
)
def test_is_gzip_compressed(trigger, content, expected):
    assert trigger.is_gzip_compressed(content) is expected


@pytest.mark.parametrize(
    "content,expected_events",
    [
        (b"data1\ndata2\ndata3", ["data1", "data2", "data3"]),
        (b"data1\ndata\xd8\ndata3", None),
    ],
)
def test_process_messages(trigger, content, expected_events):
    assert trigger.process_messages(content) == expected_events


def test_run(trigger):
    trigger.configuration.chunk_size = 1

    with (
        patch("netskope_modules.connectors.connector_pubsub_lite.AsyncSubscriberClient") as mock,
        patch(
            "netskope_modules.connectors.connector_pubsub_lite.PubSubLite.subscription_path",
            new_callable=PropertyMock,
        ) as mock_sub_path,
        patch(
            "netskope_modules.connectors.connector_pubsub_lite.AsyncSubscriberClient.subscribe",
            new_callable=AsyncMock,
        ),
        patch(
            "netskope_modules.connectors.connector_pubsub_lite.PubSubLite.load_checkpoint",
            new_callable=AsyncMock,
        ),
        patch(
            "netskope_modules.connectors.connector_pubsub_lite.PubSubLite.save_checkpoint",
            new_callable=AsyncMock,
        ),
        patch("netskope_modules.connectors.connector_pubsub_lite.AdminClient"),
    ):
        trigger.last_seen_timestamp = datetime(year=2023, month=3, day=11, hour=13, minute=21, second=23)
        mock_sub_path.return_value = "projects/13212241/subscriptions/6"
        instance = mock.return_value

        instance.__aenter__.return_value.subscribe.return_value = AsyncIterator(
            seq=[
                create_async_message(
                    b"data1",
                    datetime(year=2023, month=3, day=11, hour=13, minute=21, second=23),
                ),
                create_async_message(
                    b"data2",
                    datetime(year=2023, month=3, day=11, hour=13, minute=21, second=45),
                ),
                create_async_message(
                    b"data3",
                    datetime(year=2023, month=3, day=11, hour=13, minute=45, second=11),
                ),
            ]
        )

        asyncio.run(trigger.fetch_messages())

        assert trigger.events_queue.qsize() == 3

        try:
            asyncio.run(asyncio.wait_for(trigger.handle_queue(), timeout=3))

        except TimeoutError:
            pass

        assert trigger.push_data_to_intakes.await_count == 3
