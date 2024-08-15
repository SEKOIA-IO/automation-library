import csv
import os
import queue
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock
from time import sleep

import requests
from dateutil.parser import isoparse
from requests import Response
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.connector.workers import Worker, Workers
from sekoia_automation.storage import PersistentJSON

from gateway_cloud_services.metrics import COLLECT_EVENTS_DURATION, EVENTS_LAG, INCOMING_EVENTS, OUTCOMING_EVENTS


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
            self.log(
                message=f"Timerange in the future. Waiting {difference.total_seconds()} seconds for next batch.",
                level="info",
            )
            sleep(difference.total_seconds())

    def query_api(self) -> str | None:
        """
        Contact Skyhigh SWG API with appropriate filters and credentials
        :return: The response
        """
        self.log(
            message=f"Querying at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            f" messages associated with timerange {self.start_date.strftime('%Y-%m-%d %H:%M:%S')}"
            f" to {self.end_date.strftime('%Y-%m-%d %H:%M:%S')}",
            level="info",
        )

        self.url = (
            "https://" + self.configuration.api_domain_name + self.endpoint + str(self.configuration.customer_id)
        )
        params = {
            "filter.requestTimestampFrom": int(self.start_date.timestamp()),
            "filter.requestTimestampTo": int(self.end_date.timestamp()),
        }
        auth = requests.auth.HTTPBasicAuth(self.configuration.account_name, self.configuration.account_password)
        request_start_time = datetime.now(timezone.utc)
        response: Response = requests.get(url=self.url, headers=self.headers, auth=auth, params=params, timeout=30)

        time_elapsed = datetime.now(timezone.utc) - request_start_time
        self.log(
            message=f"Skyhigh API took {time_elapsed} to answer our query",
            level="info",
        )
        COLLECT_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
            int(time_elapsed.total_seconds())
        )

        if not response.ok:
            self.log(
                message=(
                    f"Request to SkyhighSWG API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.text}"
                ),
                level="error",
            )
            return None

        content = response.content.decode("utf-8")

        if len(content.strip("\n")) == 0:
            return None

        return content

    def run(self):  # pragma: no cover
        self.log(message="The Event Collector has started", level="info")
        self._init_time_range()

        while not self._stop_event.is_set():
            try:
                response = self.query_api()

                if response:
                    self.events_queue.put(response)
                else:
                    self.log(message="No messages to forward", level="info")
            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events")

            self._update_time_range()
            self._sleep_until_next_batch()

        self.log(message="The Event Collector has stopped", level="info")


class Transformer(Worker):
    KIND = "transformer"

    def __init__(self, connector: "SkyhighSecuritySWGTrigger", queue: queue.Queue, output_queue: queue.Queue):
        super().__init__()
        self.connector = connector
        self.configuration = connector.configuration
        self.queue = queue
        self.output_queue = output_queue

    def _transform(self, response: str) -> list[str]:
        """
        :param api_response:  events formatted as CSV
        :return: events formatted as KV
        """
        reader = csv.DictReader(response.splitlines())
        event_list: list[str] = []
        for event in reader:
            event_kv = " ".join([f"{k}={v}" for k, v in event.items()])
            event_list.append(event_kv)

        return event_list

    def run(self):
        try:
            while self.is_running or self.queue.qsize() > 0:
                try:
                    response = self.queue.get(block=True, timeout=0.5)
                    messages = self._transform(response)

                    if len(messages) > 0:
                        INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
                        self.output_queue.put(messages)
                    else:
                        self.connector.log(message="No messages to forward", level="info")
                except queue.Empty:
                    pass
        except Exception as ex:
            self.connector.log_exception(ex, message="Unexpected error when converting data")


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


class SkyhighSecuritySWGTrigger(Connector):
    configuration: SkyhighSWGConfig

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

    def run(self):  # pragma: no cover
        self.log(message="SkyhighSWG Trigger has started", level="info")

        # create the queues
        queue_size = int(os.environ.get("QUEUE_SIZE", 10000))
        collect_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        forwarding_queue: queue.Queue = queue.Queue(maxsize=queue_size)

        # start the event forwarder
        batch_size = int(os.environ.get("BATCH_SIZE", 10000))
        forwarders = Workers.create(
            int(os.environ.get("NB_FORWARDERS", 1)), EventsForwarder, self, forwarding_queue, batch_size
        )
        forwarders.start()

        # start the transformers
        transformers = Workers.create(
            int(os.environ.get("NB_TRANSFORMERS", 1)), Transformer, self, collect_queue, forwarding_queue
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
