import asyncio
import os
import time
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Optional, cast, Union

import orjson
from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, PartitionContext
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration, Connector

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, MESSAGES_AGE, OUTCOMING_EVENTS


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

    def client(self) -> EventHubConsumerClient:
        if self._client is None:
            self._client = EventHubConsumerClient.from_connection_string(
                self.configuration.hub_connection_string,
                self.configuration.hub_consumer_group,
                eventhub_name=self.configuration.hub_name,
                checkpoint_store=self.checkpoint_store,
                uamqp_transport=True,
            )

        return self._client

    async def receive_batch(self, *args: Any, **kwargs: Optional[Any]) -> None:
        try:
            # Default value for max batch size is 300 if not provided.
            await self.client().receive_batch(*args, **kwargs)  # type: ignore
        except Exception as e:
            await self.close()
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

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self._consumption_max_wait_time = int(os.environ.get("CONSUMER_MAX_WAIT_TIME", "10"), 10)  # 10 seconds default
        self._frequency = int(os.environ.get("FREQUENCY_MAX_TIME", "10"), 10)
        self._has_more_events = True

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

            # acknowledge the messages
            await partition_context.update_checkpoint()
        else:  # pragma: no cover
            # We reached the max_wait_time, close the current client
            self.log(
                message=(f"No new messages received from the last {self._frequency} seconds."),
            )

            # reset the metrics
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            MESSAGES_AGE.labels(intake_key=self.configuration.intake_key).set(0)

    @staticmethod
    def get_records_from_message(message: EventData) -> tuple[list[Any], str]:
        """
        Return the records according to the body of the message
        """
        body: Union[str, dict[str, Any]]

        try:
            body = message.body_as_json()
            if isinstance(body, list):  # handle list of events
                return body, "json"
            elif isinstance(body, dict) and "records" in body:  # handle wrapped events
                return cast(list[Any], body.get("records", [])), "json"
            elif body.get("type") == "heartbeat":  # exclude heartbeat messages
                return [], "json"
            else:
                return [body], "json"
        except:
            body = message.body_as_str()
            return [body], "str"

    async def forward_events(self, messages: list[EventData]) -> None:
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(messages))
        start = time.time()

        records = []
        for message in messages:
            body, body_type = self.get_records_from_message(message)
            for record in body:
                if record is not None:
                    if body_type == "json":
                        records.append(orjson.dumps(record).decode("utf-8"))
                    else:
                        records.append(record)

        if len(records) > 0:
            self.log(f"Forward {len(records)} events")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(records))
            await self.push_data_to_intakes(events=records)
            self._has_more_events = True
        else:
            self.log("No events to forward")
            self._has_more_events = False

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

    # Only for easy mock purposed in tests
    async def receive_events(self) -> None:
        await self.client.receive_batch(
            on_event_batch=self.handle_messages,
            on_error=self.handle_exception,
            max_wait_time=self._consumption_max_wait_time,
        )

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:  # pragma: no cover
        """
        Stop the connector
        """
        super(Connector, self).stop(*args, **kwargs)

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                await self.receive_events()

            except Exception as ex:
                self.log_exception(ex, message="Failed to consume messages")
                self._has_more_events = False

            await self.client.close()

            if not self._has_more_events:
                await asyncio.sleep(self._frequency)

        await self._session.close()

    def run(self) -> None:  # pragma: no cover
        self.log("Azure EventHub Trigger has started")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())

        self.log("Azure EventHub Trigger has stopped")
