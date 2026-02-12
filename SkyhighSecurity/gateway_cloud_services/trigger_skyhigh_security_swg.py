import csv
import os
import queue
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from itertools import batched
from threading import Lock, Thread
from time import sleep

from dateutil.parser import isoparse
from requests import Response
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.connector.workers import Worker, Workers
from sekoia_automation.storage import PersistentJSON

from gateway_cloud_services.client import ApiClient
from gateway_cloud_services.logging import get_logger
from gateway_cloud_services.metrics import COLLECT_EVENTS_DURATION, EVENTS_LAG, INCOMING_EVENTS, OUTCOMING_EVENTS

logger = get_logger()


class SkyhighSWGConfig(DefaultConnectorConfiguration):
    customer_id: int
    account_name: str
    account_password: str
    frequency: int = 20
    timedelta: int = 5  # custom lag of the trigger (ex. fetch events from 5 minutes ago)
    start_time: int = 1
    api_domain_name: str = "msg.mcafeesaas.com"


class EventCollector(Thread):
    def __init__(self, connector: "SkyhighSecuritySWGTrigger", events_queue: queue.Queue):
        super().__init__()
        self.connector = connector
        self.events_queue = events_queue
        self.trigger_activation: datetime = datetime.now(timezone.utc)
        self.headers = {"Accept": "text/csv", "x-mwg-api-version": "8"}
        self.endpoint: str = "/mwg/api/reporting/forensic/"
        self._stop_event = connector._stop_event
        self.configuration = connector.configuration
        self.end_date: datetime
        self.start_date: datetime
        self.url: str

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    @cached_property
    def client(self):
        return ApiClient(
            account_name=self.configuration.account_name,
            account_password=self.configuration.account_password,
            nb_retries=10,
        )

    def save_most_recent_date_seen(self, dt: datetime) -> None:
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            cache["most_recent_date_seen"] = dt.isoformat()
        self.connector.context_lock.release()

    def _update_time_range(self):
        self.save_most_recent_date_seen(self.end_date)

        self.start_date: datetime = self.end_date
        self.end_date: datetime = self.end_date + timedelta(seconds=self.configuration.frequency)

    def _init_time_range(self):
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")
        self.connector.context_lock.release()

        if most_recent_date_seen_str is None:
            self.end_date = self.trigger_activation - timedelta(hours=self.configuration.start_time)

            # Only apply timedelta if start_time is set to 0
            if self.configuration.start_time == 0:
                self.end_date = self.end_date - timedelta(minutes=self.configuration.timedelta)

            self.start_date = self.end_date - timedelta(seconds=self.configuration.frequency)

        else:
            self.start_date = isoparse(most_recent_date_seen_str)
            self.end_date: datetime = self.start_date + timedelta(seconds=self.configuration.frequency)

    def _sleep_until_next_batch(self):
        """
        Prevent the trigger from:
        - taking some lag
        - querying events for a timeframe in the future
        """
        now = datetime.now(timezone.utc) - timedelta(minutes=self.configuration.timedelta)

        current_lag = now - self.end_date
        self.log(
            message=f"Current lag {int(current_lag.total_seconds())} seconds.",
            level="info",
        )
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

        if self.end_date >= now:
            difference = self.end_date - now
            difference_seconds = int(difference.total_seconds())
            logger.info(
                "Timerange in the future. Waiting for next batch.",
                wait_time=difference_seconds,
            )
            sleep(difference_seconds)

    def query_api(self) -> str | None:
        """
        Contact Skyhigh SWG API with appropriate filters and credentials
        :return: The response
        """
        logger.info(
            "Querying SkyhighSWG API for events",
            start_date=self.start_date.isoformat(),
            end_date=self.end_date.isoformat(),
        )

        self.url = (
            "https://" + self.configuration.api_domain_name + self.endpoint + str(self.configuration.customer_id)
        )
        params = {
            "filter.requestTimestampFrom": int(self.start_date.timestamp()),
            "filter.requestTimestampTo": int(self.end_date.timestamp()),
        }
        request_start_time = datetime.now(timezone.utc)
        response: Response = self.client.get(url=self.url, headers=self.headers, params=params, timeout=30)

        time_elapsed = datetime.now(timezone.utc) - request_start_time
        logger.info(
            "Skyhigh API response received",
            time_elapsed_seconds=int(time_elapsed.total_seconds()),
        )
        COLLECT_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
            int(time_elapsed.total_seconds())
        )

        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"
            self.log(
                message=(
                    f"Request to SkyhighSWG API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.text}"
                ),
                level=level,
            )

        # Raise an exception for HTTP errors
        response.raise_for_status()

        content = response.content.decode("utf-8")

        if len(content.strip("\n")) == 0:
            return None

        return content

    def next_batch(self):
        """
        Fetch the next batch of events and put them in the queue

        1. Query the API
        2. If we have a response, put it in the queue
        3. Update the time range
        4. Sleep until the next batch
        """
        try:
            # 1. Query the API
            response = self.query_api()

            if response:
                # 2. If we have a response, put it in the queue
                self.events_queue.put(response)
            else:
                self.log(message="No messages to forward", level="info")

            # 3. Update the time range
            self._update_time_range()

            # 4. Sleep until the next batch
            self._sleep_until_next_batch()
        except Exception as ex:
            self.log_exception(ex, message="Failed to fetch events")

            # In case of error, wait the frequency before retrying
            sleep(self.configuration.frequency)

    def run(self):  # pragma: no cover
        logger.info("Starting Event Collector worker thread.")
        self._init_time_range()

        while not self._stop_event.is_set():
            self.next_batch()

        logger.info("Event Collector worker thread has stopped.")


class Transformer(Worker):
    KIND = "transformer"

    def __init__(
        self,
        connector: "SkyhighSecuritySWGTrigger",
        queue: queue.Queue,
        output_queue: queue.Queue,
        max_batch_size: int = 20000,
    ):
        super().__init__()
        self.connector = connector
        self.configuration = connector.configuration
        self.queue = queue
        self.output_queue = output_queue
        self.max_batch_size = max_batch_size

    def _transform(self, response: str) -> Generator[str, None, None]:
        """
        :param api_response:  events formatted as CSV
        :yield: events formatted as KV
        """
        reader = csv.DictReader(response.splitlines())
        for event in reader:
            yield " ".join([f"{k}={v}" for k, v in event.items()])

    def run(self):
        logger.info("Starting Transformer worker thread.")

        try:
            while self.is_running or self.queue.qsize() > 0:
                try:
                    response = self.queue.get(block=True, timeout=0.5)

                    # The transformation is done in batches to avoid filling the memory if we have a lot of events
                    for messages in batched(self._transform(response), self.max_batch_size):
                        if len(messages) > 0:
                            nb_events = len(messages)
                            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(nb_events)
                            logger.info("Transformed events", nb_events=nb_events)
                            self.output_queue.put(list(messages))

                except queue.Empty:
                    pass
        except Exception as ex:
            self.connector.log_exception(ex, message="Unexpected error when converting data")

        logger.info("Transformer worker thread has stopped.")


class EventsForwarder(Worker):
    KIND = "forwarder"

    def __init__(self, connector: "SkyhighSecuritySWGTrigger", queue: queue.Queue, max_batch_size: int = 20000):
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
        logger.info("Starting Events Forwarder worker thread.")

        try:
            while self.is_running or self.queue.qsize() > 0:
                events = self.next_batch(self.max_batch_size)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))

                if len(events) > 0:
                    self.connector.log(
                        message=f"Forward {len(events)} events to the intake",
                        level="info",
                    )
                    self.connector.push_events_to_intakes(events=events)
        except Exception as ex:
            self.connector.log_exception(ex, message="Failed to forward events")

        logger.info("Events Forwarder worker thread has stopped.")


class SkyhighSecuritySWGTrigger(Connector):
    configuration: SkyhighSWGConfig

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

    def run(self):  # pragma: no cover
        self.log(message="SkyhighSWG Trigger has started", level="info")

        # create the queues
        collect_queue_size = int(os.environ.get("QUEUE_SIZE", 100))
        collect_queue: queue.Queue = queue.Queue(maxsize=collect_queue_size)
        forwarding_queue_size = int(os.environ.get("FORWARDING_QUEUE_SIZE", 10000))
        forwarding_queue: queue.Queue = queue.Queue(maxsize=forwarding_queue_size)

        # start the event forwarder
        batch_size = int(os.environ.get("BATCH_SIZE", 10000))
        forwarders = Workers.create(
            int(os.environ.get("NB_FORWARDERS", 1)), EventsForwarder, self, forwarding_queue, batch_size
        )
        forwarders.start()

        # start the transformers
        transformers = Workers.create(
            int(os.environ.get("NB_TRANSFORMERS", 1)), Transformer, self, collect_queue, forwarding_queue, batch_size
        )
        transformers.start()

        # start the event collector
        collector = EventCollector(self, collect_queue)
        collector.start()

        try:
            while self.running:
                sleep(5)

                # supervise the forwarders and restart dead ones
                forwarders.supervise()

                # supervise the transformers and restart dead ones
                transformers.supervise()

                # if the collector is down, restart it
                if not collector.is_alive():
                    self.log(message="Event collector failed", level="error")
                    collector = EventCollector(self, collect_queue)
                    collector.start()

        finally:
            # Wait the collector to stop
            collector.join()

            # stop the transformers
            transformers.stop(timeout_per_worker=2)

            # stop the forwarders
            forwarders.stop(timeout_per_worker=2)
