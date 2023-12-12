import asyncio
import os
import signal
import time
from functools import cached_property
from threading import Event
from typing import Any, Optional, cast

import orjson
from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, PartitionContext
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration

from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class AzureEventsHubConfiguration(DefaultConnectorConfiguration):
    hub_connection_string: str
    hub_name: str
    hub_consumer_group: str
    storage_connection_string: str
    storage_container_name: str


class Client(object):
    _client: EventHubConsumerClient | None = None

    def __init__(self, configuration: AzureEventsHubConfiguration) -> None:
        self.configuration = configuration
        self._client = None

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
        )

    async def receive_batch(self, *args: Any, **kwargs: Optional[Any]) -> None:
        self._client = self._new_client()
        try:
            await self._client.receive_batch(*args, **kwargs)  # type: ignore
        finally:
            await self.close()

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


class AzureEventsHubTrigger(AsyncConnector):
    """
    This trigger consumes messages from Microsoft Azure EventHub
    """

    configuration: AzureEventsHubConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self._consumption_max_wait_time = int(os.environ.get("CONSUMER_MAX_WAIT_TIME", "600"), 10)

    @cached_property
    def client(self) -> Client:
        return Client(self.configuration)

    async def handle_messages(self, partition_context: PartitionContext, messages: list[EventData]) -> None:
        """
        Handle new messages
        """
        if len(messages) > 0:
            # got messages, we forward them
            await self.forward_events(messages)

        else:
            # We reached the max_wait_time, close the current client
            self.log(
                message=(
                    f"No new messages received from the last {self._consumption_max_wait_time} seconds. "
                    "Close the current client"
                ),
                level="info",
            )
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

    async def handle_exception(self, partition_context: PartitionContext, exception: Exception) -> None:
        self.log_exception(
            exception,
            message="Error raised when consuming messages",
        )

    def run(self) -> None:  # pragma: no cover
        self.log(message="Azure EventHub Trigger has started", level="info")
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    try:
                        loop.run_until_complete(
                            self.client.receive_batch(
                                on_event_batch=self.handle_messages,
                                on_error=self.handle_exception,
                                max_wait_time=self._consumption_max_wait_time,
                            )
                        )

                    except Exception as ex:
                        self.log_exception(ex, message="Failed to consume messages")
                        raise ex

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
