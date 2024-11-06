import asyncio
import os
import signal
import time
from asyncio import Task
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Optional, cast
from loguru import logger

import orjson
from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, PartitionContext
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, MESSAGES_AGE, OUTCOMING_EVENTS


class AzureEventsHubConfiguration(DefaultConnectorConfiguration):
    hub_connection_string: str
    hub_name: str
    hub_consumer_group: str
    storage_connection_string: str
    storage_container_name: str


class Client(object):
    _client: EventHubConsumerClient | None = None

    def __init__(self, configuration: AzureEventsHubConfiguration, epoch_max_value: int | None = None) -> None:
        self.configuration = configuration
        self._client = None
        self._epoch_max_value = epoch_max_value

    @cached_property
    def checkpoint_store(self) -> BlobCheckpointStore:
        return BlobCheckpointStore.from_connection_string(  # type: ignore[misc]
            self.configuration.storage_connection_string, container_name=self.configuration.storage_container_name
        )

    def _new_client(self) -> EventHubConsumerClient:
        return EventHubConsumerClient.from_connection_string(
            self.configuration.hub_connection_string,
            self.configuration.hub_consumer_group,
            eventhub_name=self.configuration.hub_name,
            checkpoint_store=self.checkpoint_store,
            uamqp_transport=True,
        )

    async def receive_batch(self, *args: Any, **kwargs: Optional[Any]) -> None:
        self._client = self._new_client()

        attempt = 0
        while True:
            try:
                await self._client.receive_batch(owner_level=attempt, *args, **kwargs)  # type: ignore
                await self.close()

                return  # exit the loop if no exception is raised
            except Exception as e:  # pragma: no cover
                logger.debug(e)
                attempt += 1
                if attempt > self._epoch_max_value:
                    logger.error(f"Failed to receive messages after multiple attempts: {e}")
                    raise e

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


class AzureEventsHubTrigger(AsyncConnector):
    """
    This trigger consumes messages from Microsoft Azure EventHub
    """

    configuration: AzureEventsHubConfiguration

    # The maximum time to wait for new messages before closing the client
    wait_timeout = 600

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self._consumption_max_wait_time = int(os.environ.get("CONSUMER_MAX_WAIT_TIME", "600"), 10)
        self._epoch_max_value = int(os.environ.get("EPOCH_MAX_VALUE", "100"), 10)
        self._current_task: Task[Any] | None = None

    @cached_property
    def client(self) -> Client:
        return Client(self.configuration, self._epoch_max_value)

    async def stop_current_task(self) -> None:
        """
        Stop the current async task
        """
        # if the current task is defined and not already cancelled
        if self._current_task is not None and not self._current_task.cancelled():
            # cancel the receiving task
            self._current_task.cancel()

            # clean the current task
            self._current_task = None

    async def shutdown(self) -> None:
        """
        Shutdown the connector
        """
        self.stop()
        await self.stop_current_task()
        self.log("Shutting down the trigger")

    async def handle_messages(self, partition_context: PartitionContext, messages: list[EventData]) -> None:
        """
        Handle new messages
        """
        if len(messages) > 0:
            # got messages, we forward them
            await self.forward_events(messages)

        else:  # pragma: no cover
            # We reached the max_wait_time, close the current client
            self.log(
                message=(
                    f"No new messages received from the last {self._consumption_max_wait_time} seconds. "
                    "Close the current client"
                ),
                level="info",
            )

            # reset the metrics
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            MESSAGES_AGE.labels(intake_key=self.configuration.intake_key).set(0)
            await self.client.close()

        # acknowledge the messages
        await partition_context.update_checkpoint()

    def get_records_from_message(self, message: EventData) -> list[Any]:
        """
        Return the records according to the body of the message
        """
        body = message.body_as_json()
        if isinstance(body, list):  # handle list of events
            return body
        elif isinstance(body, dict) and "records" in body:  # handle wrapped events
            return cast(list[Any], body.get("records", []))
        elif body.get("type") == "heartbeat":  # exclude heartbeat messages
            return []
        else:
            return [body]

    async def forward_events(self, messages: list[EventData]) -> None:
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(messages))
        start = time.time()
        records = [
            orjson.dumps(record).decode("utf-8")
            for message in messages
            for record in self.get_records_from_message(message)
            if record is not None
        ]

        if len(records) > 0:
            self.log(
                message=f"Forward {len(records)} events",
                level="info",
            )
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(records))
            await self.push_data_to_intakes(events=records)

        else:
            self.log(
                message="No events to forward",
                level="info",
            )

        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(time.time() - start)

        enqueued_times = [message.enqueued_time for message in messages if message.enqueued_time is not None]
        if len(enqueued_times) > 0:  # pragma: no cover
            now = datetime.now(timezone.utc)
            messages_age = [int((now - enqueued_time).total_seconds()) for enqueued_time in enqueued_times]

            # Compute the distance from the most recent message consumed
            current_lag = min(messages_age)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

            # Monitor the age of all messages
            for age in messages_age:
                MESSAGES_AGE.labels(intake_key=self.configuration.intake_key).set(age)

    async def handle_exception(self, partition_context: PartitionContext, exception: Exception) -> None:
        self.log_exception(
            exception,
            message="Error raised when consuming messages",
        )

    async def receive_events(self) -> None:
        try:
            await self.client.receive_batch(
                on_event_batch=self.handle_messages,
                on_error=self.handle_exception,
                max_wait_time=self._consumption_max_wait_time,
                epoch_max_value=self._epoch_max_value,
            )

        except asyncio.CancelledError:
            # Handle the cancellation properly and ensure the client is closed.
            await self.client.close()
            raise

        except Exception as ex:
            self.log_exception(ex, message="Failed to consume messages")
            raise ex

    async def async_run(self) -> None:
        while self.running:
            self._current_task = asyncio.create_task(self.receive_events())

            try:
                # Allow the task to run for the specified duration (10 minutes default)
                await asyncio.sleep(self.wait_timeout)

                # Stop the receiving task after the duration
                await self.stop_current_task()

            except asyncio.CancelledError:
                self.log(message="Receiving task was cancelled", level="info")

            finally:
                # Ensure the client is closed properly
                await self.client.close()

    def run(self) -> None:  # pragma: no cover
        self.log(message="Azure EventHub Trigger has started", level="info")

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(self.shutdown()))
        loop.add_signal_handler(signal.SIGINT, lambda: loop.create_task(self.shutdown()))
        loop.run_until_complete(self.async_run())

        self.log(message="Azure EventHub Trigger has stopped", level="info")
