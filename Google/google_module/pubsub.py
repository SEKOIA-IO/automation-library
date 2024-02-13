import os
import queue
import time
from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from threading import Event, Thread

from google.api_core import exceptions, retry
from google.cloud.pubsub_v1 import SubscriberClient, types
from google_module.base import GoogleTrigger
from google_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from pydantic import BaseModel

max_chunk_size: int = 1000


class PubSubConfig(BaseModel):
    intake_key: str
    subject_id: str
    project_id: str
    frequency: int = 20
    intake_server: str = "https://intake.sekoia.io"
    chunk_size: int = 1000


class Worker(Thread):
    KIND = "worker"

    def __init__(self):
        super().__init__()
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def is_running(self):
        return not self._stop_event.is_set()


class MessagesConsumer(Worker):
    KIND = "Consumer"

    def __init__(self, connector: "PubSub", subscription_name: str, queue: queue.Queue):
        super().__init__()
        self.connector = connector
        self.subscription_name = subscription_name
        self.queue = queue
        self.configuration = connector.configuration
        self.client: SubscriberClient | None = None

    def stop(self):
        super().stop()

        # close the client if defined
        if self.client:
            self.client.close()

    def fetch_events(self) -> Generator[list, None, None]:
        self.client = SubscriberClient()

        # Define the retry policy
        retry_policy = retry.Retry(predicate=retry.if_transient_error)

        # create the pull request
        pull_request = types.PullRequest(
            subscription=self.subscription_name,
            max_messages=self.configuration.chunk_size,
        )

        with self.client as subscriber:
            while self.is_running:
                batch_start_time = time.time()
                # pull a new set of messages (with retry for transient errors)
                response = subscriber.pull(request=pull_request, retry=retry_policy)

                # get contents and ack_ids from messages
                messages = []
                ack_ids = []
                most_recent_date_seen = None
                for message in response.received_messages:
                    messages.append(message.message.data.decode("utf-8"))
                    ack_ids.append(message.ack_id)

                    # look for the most recent publication date in messages
                    message_date = message.message.publish_time
                    if message_date is not None and (
                        most_recent_date_seen is None or message_date > most_recent_date_seen
                    ):
                        most_recent_date_seen = message_date

                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(messages))

                # ack the messages if defined
                if len(ack_ids) > 0:
                    subscriber.acknowledge(request={"subscription": self.subscription_name, "ack_ids": ack_ids})

                if len(messages) > 0:
                    # Compute the current lag
                    if not most_recent_date_seen:
                        self.connector.log("unable to get publication date from messages", level="warning")
                    else:
                        now = datetime.now(timezone.utc)
                        current_lag = now - most_recent_date_seen
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                            int(current_lag.total_seconds())
                        )

                    yield messages
                else:
                    batch_duration = time.time() - batch_start_time
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)
                    delta_sleep = self.configuration.frequency - batch_duration
                    if delta_sleep > 0:
                        time.sleep(delta_sleep)

    def run(self):
        while self.is_running:
            try:
                for messages in self.fetch_events():
                    self.queue.put(messages)
            except exceptions.Cancelled:
                pass
            except Exception as ex:
                self.connector.log_exception(ex, message=f"failed to fetch messages from {self.subscription_name}")


class EventsForwarder(Worker):
    KIND = "forwarder"

    def __init__(self, connector: "PubSub", queue: queue.Queue, max_batch_size: int = 20000):
        super().__init__()
        self.connector = connector
        self.configuration = connector.configuration
        self.queue = queue
        self.max_batch_size = max_batch_size

    def next_batch(self, max_batch_size: int) -> list:
        events = []
        while self.is_running:
            try:
                messages = self.queue.get(block=True, timeout=0.5)

                if len(messages) > 0:
                    events.extend(messages)

                if len(events) >= max_batch_size:
                    break

            except queue.Empty:
                break

        return events

    def run(self):
        try:
            while self.is_running or self.queue.qsize() > 0:
                events = self.next_batch(self.max_batch_size)

                if len(events) > 0:
                    self.connector.log(
                        message=f"Forward {len(events)} events to the intake",
                        level="info",
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                    self.connector.push_events_to_intakes(events=events)
        except Exception as ex:
            self.connector.log_exception(ex, message="Failed to forward events")


class PubSub(GoogleTrigger):
    """
    Connect to Google Cloud PubSub API and return the results (PubSub works like kafka)
    """

    configuration: PubSubConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client: SubscriberClient | None = None

    @cached_property
    def subscription_name(self) -> str:
        """
        Return the subscription name
        """
        return SubscriberClient.subscription_path(self.configuration.project_id, self.configuration.subject_id)

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Google Cloud PubSub connector", level="info")
        super().stop(*args, **kwargs)

    def create_workers(self, nb_workers: int, klass: type[Worker], *args, **kwargs) -> list[Worker]:
        return [klass(*args, **kwargs) for _ in range(nb_workers)]

    def supervise_workers(self, workers: list[Worker], klass: type[Worker], *args, **kwargs):
        for index in range(len(workers)):
            if not workers[index].is_alive() and workers[index].is_running:
                self.log(message=f"Restart a {klass.KIND}", level="warning")
                workers[index] = klass(*args, **kwargs)
                workers[index].start()

    def start_workers(self, workers: list[Worker]):
        for worker in workers:
            worker.start()

    def stop_workers(self, workers: list[Worker], timeout=None):
        timeout_per_worker = min(timeout / len(workers), 0.5) if timeout else None

        for worker in workers:
            if worker.is_alive():
                worker.stop()

        for worker in workers:
            worker.join(timeout=timeout_per_worker)

    def run(self) -> None:  # pragma: no cover
        self.log(
            message=f"Starting Google Cloud Pubsub subscription to {self.subscription_name}",
            level="info",
        )

        # create the events queue
        events_queue_size = int(os.environ.get("QUEUE_SIZE", 10000))
        events_queue: queue.Queue = queue.Queue(maxsize=events_queue_size)

        # start the event forwarders
        batch_size = int(os.environ.get("BATCH_SIZE", 10000))
        forwarders = self.create_workers(
            int(os.environ.get("NB_FORWARDERS", 1)), EventsForwarder, self, events_queue, max_batch_size=batch_size
        )
        self.start_workers(forwarders)

        # start the consumers
        consumers = self.create_workers(
            int(os.environ.get("NB_CONSUMERS", 1)), MessagesConsumer, self, self.subscription_name, events_queue
        )
        self.start_workers(consumers)

        while self.running:
            # Wait 5 seconds for the next supervision
            time.sleep(5)

            self.supervise_workers(forwarders, EventsForwarder, self, events_queue, max_batch_size=batch_size)
            self.supervise_workers(consumers, MessagesConsumer, self, self.subscription_name, events_queue)

        # Stop the consumer
        self.stop_workers(consumers, timeout=2)

        # Ensure that all events are forwarded
        if events_queue.qsize() > 0:
            self.supervise_workers(forwarders, EventsForwarder, self, events_queue, max_batch_size=batch_size)

        # Stop the forward
        self.stop_workers(forwarders)

        # Stop the connector executor
        self._executor.shutdown(wait=True)
