import os
import queue
import time
from datetime import datetime, timezone
from enum import Enum
from functools import cached_property
from posixpath import join as urljoin
from threading import Event, Thread
from urllib.parse import urlencode

import orjson
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from websocket import WebSocketApp, WebSocketTimeoutException

from proofpoint_modules.helpers import format_datetime, normalize_since_time, split_message
from proofpoint_modules.metrics import EVENTS_LAG, INCOMING_EVENTS, OUTCOMING_EVENTS
from proofpoint_modules.pod.checkpoint import Checkpoint


class PODMessageType(str, Enum):
    MESSAGE = "message"
    MAILLOG = "maillog"


class PODConfig(DefaultConnectorConfiguration):
    api_host: str
    api_key: str
    cluster_id: str
    type: PODMessageType
    since_time: str | None = None


class PoDEventsConsumer(Thread):
    def __init__(self, connector: "PoDEventsTrigger", queue: queue.Queue, checkpoint: Checkpoint):
        super().__init__()
        self.connector = connector
        self.queue = queue
        self.configuration = connector.configuration
        self.most_recent_date_seen: datetime | None = checkpoint.offset
        self.websocket: WebSocketApp | None = None
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

        # close the websocket
        if self.websocket:
            self.websocket.close()

    @property
    def is_running(self):
        return not self._stop_event.is_set()

    @cached_property
    def since_time(self) -> datetime:
        return normalize_since_time(self.configuration.since_time)

    @property
    def url(self):
        params = {
            "cid": self.configuration.cluster_id,
            "type": self.configuration.type.value,
        }
        since_time = self.most_recent_date_seen or self.since_time
        if since_time:
            params["sinceTime"] = format_datetime(since_time)

        parameters = urlencode(params)
        url = urljoin(self.configuration.api_host, "v1", "stream")
        return f"{url}?{parameters}"

    def create_websocket(self, url):
        headers = [f"Authorization: Bearer {self.configuration.api_key}"]
        return WebSocketApp(
            url=url,
            header=headers,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    def on_error(self, _, error):
        if isinstance(error, WebSocketTimeoutException):
            # add a gentler message for timeout
            self.connector.log(message="Websocket timed out", level="warning")
        else:
            self.connector.log(message=f"Websocket error: {error}", level="error")

    def on_close(self, *_):
        self.connector.log(message="Closing socket connection", level="info")

    def on_message(self, _, event) -> None:
        try:
            message = orjson.loads(event)
            message["type"] = self.configuration.type.value
            self.most_recent_date_seen = message.get("ts")

            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
            self.queue.put((self.most_recent_date_seen, message))
        except Exception as ex:
            self.connector.log_exception(ex, message="Failed to consume event")

    def run(self):  # pragma: nocover
        self.connector.log(message=f"Connection to stream {self.url}", level="info")

        while self.is_running:
            self.websocket = self.create_websocket(self.url)
            teardown = self.websocket.run_forever()

            # The worker is stopping, exit here
            if not self.is_running:
                return

            if not teardown:
                self.connector.log("Websocket event loop stopped for an unknwon reason", level="error")

            self.connector.log("Failure in the websocket event loop", level="warning")


class EventsForwarder(Thread):
    def __init__(
        self, connector: "PoDEventsTrigger", queue: queue.Queue, checkpoint: Checkpoint, max_batch_size: int = 20000
    ):
        super().__init__()
        self.connector = connector
        self.queue = queue
        self.checkpoint = checkpoint
        self.configuration = connector.configuration
        self.max_batch_size = max_batch_size
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def is_running(self):
        return not self._stop_event.is_set()

    def next_batch(self, max_batch_size: int) -> list:
        events = []
        most_recent_date_seen_str = None
        while self.is_running:
            try:
                (timestamp_str, message) = self.queue.get(block=True, timeout=0.5)

                if message.get("type") == "message" and "msgParts" in message and "guid" in message:
                    events.extend(split_message(message))
                else:
                    events.append(orjson.dumps(message).decode("utf-8"))

                if most_recent_date_seen_str is None or timestamp_str > most_recent_date_seen_str:
                    most_recent_date_seen_str = timestamp_str

                if len(events) >= max_batch_size:
                    break

            except queue.Empty:
                break

        if most_recent_date_seen_str is not None:
            most_recent_date_seen = isoparse(most_recent_date_seen_str)
            self.checkpoint.offset = most_recent_date_seen

            # compute the lag
            now = datetime.now(timezone.utc)
            current_lag = now - most_recent_date_seen
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

        return events

    def run(self):
        while self.is_running or self.queue.qsize() > 0:
            try:
                events = self.next_batch(self.max_batch_size)

                if len(events) > 0:
                    self.connector.log(
                        message=f"Forward {len(events)} events to the intake",
                        level="info",
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                    self.connector.push_events_to_intakes(events=events)
            except Exception as ex:
                self.connector.log_exception(ex, message="Failed to forward event")


class PoDEventsTrigger(Connector):
    """
    The Proofpoint PoD trigger listen events from the PoD Log service
    """

    configuration: PODConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Proofpoint PoD connector", level="info")
        super().stop(*args, **kwargs)

    def run(self):  # pragma: no cover
        self.log(message="ProofPoint PoD Events Trigger has started", level="info")

        # Load the checkpoint
        checkpoint = Checkpoint(self._data_path)

        # create the events queue
        events_queue_size = int(os.environ.get("QUEUE_SIZE", 10000))
        events_queue: queue.Queue = queue.Queue(maxsize=events_queue_size)

        # start the consumer
        consumer = PoDEventsConsumer(self, events_queue, checkpoint)
        consumer.start()

        # start the event forwarder
        batch_size = int(os.environ.get("BATCH_SIZE", 10000))
        forwarder = EventsForwarder(self, events_queue, checkpoint, max_batch_size=batch_size)
        forwarder.start()

        while self.running:
            # Wait 5 seconds for the next supervision
            time.sleep(5)

            # if the read queue thread is down, we spawn a new one
            if not forwarder.is_alive() and forwarder.is_running:
                self.log(message="Restart event forwarder", level="warning")
                forwarder = EventsForwarder(self, events_queue, checkpoint, max_batch_size=batch_size)
                forwarder.start()

            # if the consumer is dead, we spawn a new one
            if not consumer.is_alive() and consumer.is_running:
                self.log(message="Restart event consumer", level="warning")

                consumer = PoDEventsConsumer(self, events_queue, checkpoint)
                consumer.start()

        # Stop the consumer
        if consumer.is_alive():
            consumer.stop()
            consumer.join(timeout=2)

        # Stop the forward
        if forwarder.is_alive():
            forwarder.stop()
            forwarder.join(timeout=5)

        # Stop the connector executor
        self._executor.shutdown(wait=True)
