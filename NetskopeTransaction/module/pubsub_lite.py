import asyncio
import gzip
import time
from functools import cached_property
from typing import AsyncIterator

from google.cloud.pubsublite.cloudpubsub import AsyncSubscriberClient
from google.cloud.pubsublite.types import CloudRegion, CloudZone, FlowControlSettings, SubscriptionPath
from pydantic import BaseModel

from .base import AsyncGoogleTrigger
from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class PubSubLiteConfig(BaseModel):
    project_id: str
    cloud_region: str
    zone_id: str | None = None
    subscription_id: str

    frequency: int = 20
    intake_server: str = "https://intake.sekoia.io"
    intake_key: str
    chunk_size: int = 1000


class PubSubLite(AsyncGoogleTrigger):
    configuration: PubSubLiteConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.events_queue = asyncio.Queue(maxsize=1000)

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Google Cloud PubSub connector", level="info")
        super().stop(*args, **kwargs)

    @cached_property
    def location(self) -> CloudZone | CloudRegion:
        if self.configuration.zone_id:
            return CloudZone(CloudRegion(self.configuration.cloud_region), self.configuration.zone_id)

        else:
            return CloudRegion(self.configuration.cloud_region)

    @cached_property
    def subscription_path(self) -> SubscriptionPath:
        return SubscriptionPath(
            project=self.configuration.project_id,
            location=self.location,
            name=self.configuration.subscription_id,
        )

    def is_gzip_compressed(self, content: bytes) -> bool:
        """
        Check if the current object is compressed with gzip
        """
        # check the magic number
        return content[0:2] == b"\x1f\x8b"

    async def handle_queue(self):
        batch_size = min(self.configuration.chunk_size, self.events_queue.maxsize)
        batch_max_wait = 30  # seconds to wait for batch to reach `batch_size`, otherwise - push available events

        batch_start = None
        batch = []

        while self.running:
            event = await self.events_queue.get()
            if not batch_start:
                batch_start = time.time()  # for a correct cold start

            batch.append(event)

            if len(batch) >= batch_size or (len(batch) > 0 and time.time() - batch_start > batch_max_wait):
                self.log(
                    message=f"Forward {len(batch)} events to the intake",
                    level="info",
                )
                await self.push_data_to_intakes(events=batch)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch))

                batch_end = time.time()
                batch_duration = batch_end - batch_start
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

                batch = []
                batch_start = time.time()

    async def fetch_messages(self):
        subscription_path = SubscriptionPath(
            self.configuration.project_id,
            self.location,
            self.configuration.subscription_id,
        )
        per_partition_flow_control_settings = FlowControlSettings(
            messages_outstanding=1000,
            bytes_outstanding=10 * 1024 * 1024,
        )

        # Forward events in the "background"
        asyncio.create_task(self.handle_queue())

        async with AsyncSubscriberClient() as subscriber_client:
            subscriber: AsyncIterator = await subscriber_client.subscribe(
                subscription=subscription_path,
                per_partition_flow_control_settings=per_partition_flow_control_settings,
            )
            async for message in subscriber:
                message_content = (
                    gzip.decompress(message.data) if self.is_gzip_compressed(message.data) else message.data
                )
                events = self.process_messages(message_content)

                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                for event in events:
                    await self.events_queue.put(event)

                message.ack()

    def process_messages(self, content: bytes) -> list[str]:
        # Netskope is putting multiple transaction events in 1 PubSub Lite message
        return [event for event in content.decode("utf-8").split("\n") if len(event) > 0]

    def run(self) -> None:  # pragma: no cover
        self.log(message="PubSub Lite connector has started", level="info")
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    try:
                        loop.run_until_complete(self.fetch_messages())

                    except Exception as ex:
                        self.log_exception(ex, message="Failed to consume messages")
                        raise ex

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
