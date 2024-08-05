import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from google.cloud.pubsub_v1.subscriber.message import Message
from pytest import fixture
import pytest

from netskope_modules.connector_pubsub_lite import PubSubLite


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
def events_queue():
    return asyncio.Queue()


@fixture
def trigger(credentials):
    trigger = PubSubLite()
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


@pytest.mark.parametrize(
    "content,expected_events",
    [(b"data1\ndata2\ndata3", ["data1", "data2", "data3"]), (b"data1\ndata\xd8\ndata3", None)],
)
def test_process_messages(trigger, content, expected_events):
    assert trigger.process_messages(content) == expected_events


def test_run(trigger, events_queue):
    trigger.configuration.chunk_size = 1

    with (
        patch("netskope_modules.connector_pubsub_lite.AsyncSubscriberClient") as mock,
        patch(
            "netskope_modules.connector_pubsub_lite.PubSubLite.subscription_path", new_callable=PropertyMock
        ) as mock_sub_path,
        patch(
            "netskope_modules.connector_pubsub_lite.AsyncSubscriberClient.subscribe", new_callable=AsyncMock
        ) as mock_subscribe,
        patch(
            "netskope_modules.connector_pubsub_lite.PubSubLite.load_checkpoint", new_callable=AsyncMock
        ) as mock_load,
        patch(
            "netskope_modules.connector_pubsub_lite.PubSubLite.save_checkpoint", new_callable=AsyncMock
        ) as mock_save,
        patch("netskope_modules.connector_pubsub_lite.AdminClient") as mock_seek,
    ):
        trigger.last_seen_timestamp = datetime(year=2023, month=3, day=11, hour=13, minute=21, second=23)
        mock_sub_path.return_value = "projects/13212241/subscriptions/6"
        instance = mock.return_value

        instance.__aenter__.return_value.subscribe.return_value = AsyncIterator(
            seq=[
                create_async_message(b"data1", datetime(year=2023, month=3, day=11, hour=13, minute=21, second=23)),
                create_async_message(b"data2", datetime(year=2023, month=3, day=11, hour=13, minute=21, second=45)),
                create_async_message(b"data3", datetime(year=2023, month=3, day=11, hour=13, minute=45, second=11)),
            ]
        )

        asyncio.run(trigger.fetch_messages())

        assert trigger.events_queue.qsize() == 3

        try:
            asyncio.run(asyncio.wait_for(trigger.handle_queue(), timeout=3))

        except TimeoutError:
            pass

        assert trigger.push_data_to_intakes.await_count == 3
