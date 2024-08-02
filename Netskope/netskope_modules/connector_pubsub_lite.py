import asyncio
import datetime
import gzip
import json
import os
import time
from functools import cached_property
from pathlib import Path
from typing import Any

from google.cloud.pubsublite import AdminClient
from google.cloud.pubsublite.cloudpubsub import AsyncSubscriberClient
from google.cloud.pubsublite.types import CloudRegion, CloudZone, FlowControlSettings, PublishTime, SubscriptionPath
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class PubSubLiteConfig(DefaultConnectorConfiguration):
    cloud_region: str
    zone_id: str | None = None
    subscription_id: str
    credentials: Any

    chunk_size: int = 1000


class PubSubLite(AsyncConnector):
    configuration: PubSubLiteConfig

    CREDENTIALS_PATH = Path("/tmp/credentials.json")
    metric_label_type = "pubsublite"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.events_queue = asyncio.Queue(maxsize=1000)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = asyncio.Lock()

        self.last_seen_timestamp: datetime.datetime = datetime.datetime.now().astimezone() - datetime.timedelta(
            minutes=5
        )
        self.latest_event_lag: float = -1

    def execute(self) -> None:
        self.set_credentials()
        super().execute()

    def set_credentials(self) -> None:
        """
        Save the credentials in a file so they can be used by the Google client
        """
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.CREDENTIALS_PATH)
        with self.CREDENTIALS_PATH.open("w") as fp:
            json.dump(self.configuration.credentials, fp)

    async def load_checkpoint(self) -> None:
        await self.context_lock.acquire()

        with self.context as cache:
            last_seen_timestamp = cache.get("last_timestamp")

        self.context_lock.release()

        if last_seen_timestamp:
            self.last_seen_timestamp = datetime.datetime.fromtimestamp(float(last_seen_timestamp)).astimezone()

    async def save_checkpoint(self) -> None:
        await self.context_lock.acquire()

        with self.context as cache:
            cache["last_timestamp"] = self.last_seen_timestamp.replace(tzinfo=datetime.timezone.utc).timestamp()

        self.context_lock.release()

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
            project=self.configuration.credentials["project_id"],
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

        while self.running or self.events_queue.qsize() > 0:
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
                await self.save_checkpoint()

                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, type=self.metric_label_type).inc(
                    len(batch)
                )

                batch_end = time.time()
                batch_duration = batch_end - batch_start
                FORWARD_EVENTS_DURATION.labels(
                    intake_key=self.configuration.intake_key, type=self.metric_label_type
                ).observe(batch_duration)

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.metric_label_type).set(
                    self.latest_event_lag
                )

                batch = []
                batch_start = time.time()

    async def fetch_messages(self):
        await self.load_checkpoint()

        per_partition_flow_control_settings = FlowControlSettings(
            messages_outstanding=1000,
            bytes_outstanding=10 * 1024 * 1024,
        )

        async with AsyncSubscriberClient() as subscriber_client:
            if self.last_seen_timestamp:
                admin_client = AdminClient(CloudRegion(self.configuration.cloud_region))
                ts_datetime = self.last_seen_timestamp.astimezone(datetime.timezone.utc) + datetime.timedelta(
                    microseconds=1
                )
                self.log("Getting events from %s" % ts_datetime.isoformat())

                ts = PublishTime(ts_datetime)
                admin_client.seek_subscription(self.subscription_path, ts)

            subscriber = await subscriber_client.subscribe(
                subscription=self.subscription_path,
                per_partition_flow_control_settings=per_partition_flow_control_settings,
            )

            async for message in subscriber:
                self.last_seen_timestamp = message.publish_time
                self.latest_event_lag = time.time() - self.last_seen_timestamp.timestamp()

                message_content = (
                    gzip.decompress(message.data) if self.is_gzip_compressed(message.data) else message.data
                )
                events = self.process_messages(message_content)

                # Put events in the forwarding queue
                if events is not None:
                    INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                    for event in events:
                        await self.events_queue.put(event)

                message.ack()

    def process_messages(self, content: bytes) -> list[str] | None:
        # Netskope is putting multiple transaction events in 1 PubSub Lite message
        try:
            return [event for event in content.decode("utf-8").split("\n") if len(event) > 0]
        except Exception:
            self.log(level="error", message="Unable to decode the content of a message")
            logger.error("Failed to decode the content of a message", content=content)
            return None

    def run(self) -> None:  # pragma: no cover
        self.log(message="PubSub Lite connector has started", level="info")

        forwarder = None
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                # Forward events in the "background"
                if not forwarder:
                    forwarder = loop.create_task(self.handle_queue())

                while self.running:
                    try:
                        loop.run_until_complete(self.fetch_messages())

                    except Exception as ex:
                        self.log_exception(ex, message="Failed to consume messages")
                        raise ex

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
