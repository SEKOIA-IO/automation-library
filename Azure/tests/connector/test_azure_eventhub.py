import asyncio
import os
import time
from multiprocessing import Process
from shutil import rmtree
from tempfile import mkdtemp
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from azure.eventhub import EventData
from sekoia_automation import constants
from sekoia_automation.module import Module

from connectors.azure_eventhub import AzureEventsHubConfiguration, AzureEventsHubTrigger, Client


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

    loop = asyncio.new_event_loop()

    def run_trigger(trigger, loop):
        asyncio.set_event_loop(loop)

        trigger.run()

    thread = Thread(target=run_trigger, args=(trigger, loop))
    thread.start()
    time.sleep(30)
    trigger.shutdown(9, loop)
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


@pytest.mark.asyncio
async def test_handle_messages(trigger):
    # arrange
    events: list[str] = [
        '{"records": [{"name": "record1"}, null, {"name": "record2"}]}',
        '{"type": "heartbeat"}',
        '[{"name": "record3"}, {"name": "record4"}, {"name": "record5"}]',
        '{"name": "record6"}',
    ]
    messages: list[EventData] = [EventData(event) for event in events]
    partition_context = AsyncMock()

    # act
    await trigger.handle_messages(partition_context, messages)

    # assert
    assert partition_context.update_checkpoint.called
    calls = [record for call in trigger.push_data_to_intakes.await_args_list for record in call.kwargs["events"]]
    assert len(calls) == 6


@pytest.mark.asyncio
async def test_client_receive_batch():
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
    client._client = consumer

    await client.receive_batch()

    consumer.receive_batch.assert_awaited_once()
    consumer.close.assert_not_called()


@pytest.mark.asyncio
async def test_client_receive_batch_with_error():
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
    client._client = consumer

    def raise_error():
        raise ValueError("Error")

    consumer.receive_batch.side_effect = raise_error
    with pytest.raises(ValueError):
        await client.receive_batch()

    consumer.receive_batch.assert_awaited_once()
    consumer.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_close():
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

    await client.close()  # nothing happens

    fake_client = AsyncMock()
    client._client = fake_client
    await client.close()

    fake_client.close.assert_awaited_once()
    assert client._client is None


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


class AzureEventsHubTestTriggerQuick(AzureEventsHubTrigger):
    # Override wait timeout to speed up the test execution and mock receive_events method
    # In this case, we will sleep for 2 second and execute for 1 second
    # So no task cancellation will happen
    execution_time = 1

    async def receive_events(self) -> None:
        await asyncio.sleep(self.execution_time)


class AzureEventsHubTestTriggerSlow(AzureEventsHubTestTriggerQuick):
    # Override wait timeout to speed up the test execution and mock receive_events method
    # In this case, we will sleep for 1 second and execute for 2 second
    # So task cancellation will happen each iteration
    execution_time = 2


def create_and_run_connector(data_storage, is_quick: bool = True) -> None:
    """
    This function is used to test the AzureEventsHubTrigger run method and receiving signals to stop the connector.

    We should run it in separate process!

    Args:
        data_storage:
        is_quick:
    """
    module = Module()

    connector = AzureEventsHubTestTriggerQuick(module=module, data_path=data_storage)
    if not is_quick:
        connector = AzureEventsHubTestTriggerSlow(module=module, data_path=data_storage)

    connector.configuration = AzureEventsHubConfiguration.parse_obj(
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

    connector.run()


def test_azure_eventhub_handling_stop_event_quick_10_seconds(data_storage):
    start_execution_time = time.time()
    process = Process(target=create_and_run_connector, args=(data_storage,))
    process.start()

    # So we can say that 1 iteration will take 2 seconds for quick connector
    # 1 second for execution and 2 seconds for waiting the result
    # Lets try to stop the connector after 5 seconds, so it should finish the execution not waiting for the next iteration
    # So the total execution time should be less or equal to 6 seconds + 1 second for
    # the possible timing difference calculation
    time.sleep(5)
    process.terminate()
    process.join()
    finish_execution_time = time.time()

    assert finish_execution_time - start_execution_time <= 11


def test_azure_eventhub_handling_stop_event_slow_10_seconds(data_storage):
    start_execution_time = time.time()
    process = Process(target=create_and_run_connector, args=(data_storage, False))
    process.start()

    # So we can say that 1 iteration will take 2 seconds for quick connector
    # 2 second for execution and 1 seconds for waiting the result
    # Lets try to stop the connector after the same 4 seconds, so behaviour should be more-less the same.
    # So the total execution time should be less or equal to 4 seconds + 1 second for
    # the possible timing difference calculation
    time.sleep(4)
    process.terminate()
    process.join()
    finish_execution_time = time.time()

    assert finish_execution_time - start_execution_time <= 11


def test_azure_eventhub_handling_stop_event_slow_20_seconds(data_storage):
    start_execution_time = time.time()
    process = Process(target=create_and_run_connector, args=(data_storage, False))
    process.start()

    time.sleep(10)
    process.terminate()
    process.join()
    finish_execution_time = time.time()

    assert finish_execution_time - start_execution_time <= 21


def test_get_records_from_message_json():
    # arrange
    body = '{"records": [{"name": "record1"}, null, {"name": "record2"}]}'
    message = EventData(body=body)

    # act
    records = AzureEventsHubTrigger.get_records_from_message(message)

    # assert
    assert len(records[0]) == 3
    assert records[0][0] == {"name": "record1"}
    assert records[0][2] == {"name": "record2"}


def test_get_records_from_message_str():
    # arrange
    body = "teststring"
    message = EventData(body=body)

    # act
    records = AzureEventsHubTrigger.get_records_from_message(message)

    # assert
    assert len(records[0]) == 1
    assert records[0][0] == "teststring"
