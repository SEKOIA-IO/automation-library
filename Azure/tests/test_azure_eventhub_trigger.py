import asyncio
import os
import time
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from azure.eventhub import EventData

from connectors.trigger_azure_eventhub import AzureEventsHubConfiguration, AzureEventsHubTrigger, Client


@pytest.mark.skipif(
    "{'AZURE_HUB_CONNECTION_STRING', 'AZURE_HUB_NAME', 'AZURE_STORAGE_CONNECTION_STRING',"
    " 'AZURE_STORAGE_CONTAINER_NAME'}.issubset(os.environ.keys()) == False"
)
def test_forward_next_batches_integration(symphony_storage):
    trigger = AzureEventsHubTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "chunk_size": 1,
        "hub_connection_string": os.environ["AZURE_HUB_CONNECTION_STRING"],
        "hub_name": os.environ["AZURE_HUB_NAME"],
        "hub_consumer_group": os.environ.get("AZURE_CONSUMER_GROUP", "$Default"),
        "storage_connection_string": os.environ["AZURE_STORAGE_CONNECTION_STRING"],
        "storage_container_name": os.environ["AZURE_STORAGE_CONTAINER_NAME"],
        "intake_key": "",
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    thread = Thread(target=trigger.run)
    thread.start()
    time.sleep(30)
    trigger.client.close()
    trigger.stop()
    calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]

    assert len(calls) > 0


@pytest.fixture
def trigger(symphony_storage):
    trigger = AzureEventsHubTrigger(data_path=symphony_storage)
    trigger.module.configuration = {}
    trigger.configuration = {
        "chunk_size": 1,
        "hub_connection_string": "hub_connection_string",
        "hub_name": "hub_name",
        "hub_consumer_group": "hub_consumer_group",
        "storage_connection_string": "storage_connection_string",
        "storage_container_name": "storage_container_name",
        "intake_key": "",
    }
    trigger.push_data_to_intakes = AsyncMock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    yield trigger


def test_handle_messages(trigger):
    # arrange
    messages: list[EventData] = [
        EventData('{"records": [{"name": "record1"}, null, {"name": "record2"}]}'),
        EventData('{"type": "heartbeat"}'),
        EventData('[{"name": "record3"}, {"name": "record4"}, {"name": "record5"}]'),
        EventData('{"name": "record6"}'),
    ]
    partition_context = AsyncMock()

    # act
    asyncio.run(trigger.handle_messages(partition_context, messages))

    # assert
    assert partition_context.update_checkpoint.called
    calls = [record for call in trigger.push_data_to_intakes.await_args_list for record in call.kwargs["events"]]
    assert len(calls) == 6


def test_client_receive_batch():
    client = Client(
        AzureEventsHubConfiguration.parse_obj(
            {
                "chunk_size": 1,
                "hub_connection_string": "hub_connection_string",
                "hub_name": "hub_name",
                "hub_consumer_group": "hub_consumer_group",
                "storage_connection_string": "storage_connection_string",
                "storage_container_name": "storage_container_name",
                "intake_key": "",
            }
        )
    )
    consumer = AsyncMock()
    client._new_client = MagicMock(return_value=consumer)

    asyncio.run(client.receive_batch())

    assert client._new_client.called
    consumer.receive_batch.assert_awaited_once()
    consumer.close.assert_awaited_once()


def test_client_close():
    client = Client(
        AzureEventsHubConfiguration.parse_obj(
            {
                "chunk_size": 1,
                "hub_connection_string": "hub_connection_string",
                "hub_name": "hub_name",
                "hub_consumer_group": "hub_consumer_group",
                "storage_connection_string": "storage_connection_string",
                "storage_container_name": "storage_container_name",
                "intake_key": "",
            }
        )
    )
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client.close())  # nothing happens

    fake_client = AsyncMock()
    client._client = fake_client
    loop.run_until_complete(client.close())

    fake_client.close.assert_awaited_once()
    assert client._client is None
