import time
import traceback
import urllib.parse
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Generator

import orjson
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import TrendMicroModule
from .client import ApiClient
from .helpers import iso8601_to_timestamp, unixtime_to_iso8601
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class TrendMicroConnectorConfiguration(DefaultConnectorConfiguration):
    service_url: str = Field(..., description="Service URL")
    username: str = Field(..., description="Username")
    api_key: str = Field(..., description="API key", secret=True)
    frequency: int = 60
    batch_size: int = 500


class TrendMicroWorker(Thread):
    API_VERSION = "v1"

    def __init__(self, connector: "TrendMicroEmailSecurityConnector", log_type: str):
        super().__init__()

        self.log_type = log_type
        self.connector = connector

        self.service_url = connector.configuration.service_url
        if self.service_url.startswith("http://"):
            self.service_url = "https://%s" % self.service_url[7:]

        elif not self.service_url.startswith("https://"):
            self.service_url = "https://%s" % self.service_url

        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @property
    def frequency(self):
        return self.connector.configuration.frequency

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(username=self.connector.configuration.username, api_key=self.connector.configuration.api_key)

    def get_last_timestamp(self) -> int:
        now = int(time.time())  # in seconds

        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_ts_seen = cache.get(self.log_type, {}).get("last_timestamp")
        self.connector.context_lock.release()

        # if undefined, retrieve events from the last 5 minutes
        if most_recent_ts_seen is None:
            return now - 5 * 60

        # We can't retrieve messages older than 72 hours
        one_week_ago = now - 72 * 60 * 60
        if most_recent_ts_seen < one_week_ago:
            most_recent_ts_seen = one_week_ago

        return most_recent_ts_seen

    def set_last_timestamp(self, last_timestamp: int) -> None:
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            cache[self.log_type] = {"last_timestamp": last_timestamp}

        self.connector.context_lock.release()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def request_logs_page(self, params: dict) -> dict | None:
        url = f"{self.service_url}/api/{self.API_VERSION}/log/mailtrackinglog"
        response = self.client.get(url, params=params, timeout=60)

        if not response.ok:
            self.log(
                message=(
                    f"Request on Trend Micro Email Security API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return None

        else:
            content = response.json() if len(response.content) > 0 else None
            return content

    def iterate_through_pages(self, from_timestamp: int) -> Generator[list, None, None]:
        timestamp_now = int(time.time())
        params = {
            "type": self.log_type,
            "start": unixtime_to_iso8601(from_timestamp),
            "end": unixtime_to_iso8601(timestamp_now),
            "limit": self.connector.configuration.batch_size,
        }
        content = self.request_logs_page(params=params)

        while self.running:
            if content is None:
                self.log(
                    message=f"{self.log_type}: No events to forward. Waiting {self.frequency} seconds",
                    level="info",
                )
                time.sleep(self.frequency)
                return

            events = content.get("logs")
            next_token = content.get("nextToken")

            if events and len(events) > 0:
                yield events

            else:
                return

            if next_token is not None:
                params["token"] = urllib.parse.unquote(next_token)  # it's provided url-encoded by API

            else:
                return

            content = self.request_logs_page(params=params)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_timestamp_seen = self.get_last_timestamp()

        for next_events in self.iterate_through_pages(most_recent_timestamp_seen):
            if next_events:
                last_event = max(next_events, key=lambda x: iso8601_to_timestamp(x.get("genTime")))
                last_event_timestamp = iso8601_to_timestamp(last_event.get("genTime"))

                if last_event_timestamp > most_recent_timestamp_seen:
                    most_recent_timestamp_seen = last_event_timestamp + 1
                    self.set_last_timestamp(most_recent_timestamp_seen)

                events_lag = int(time.time()) - most_recent_timestamp_seen
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).set(
                    events_lag
                )

                yield next_events

    def next_batch(self):
        batch_start_time = time.time()

        # Iterate through batches
        try:
            events = next(self.fetch_events())
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"{self.log_type}: Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).inc(
                    len(batch_of_events)
                )

                self.connector.push_events_to_intakes(events=batch_of_events)

                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).inc(
                    len(batch_of_events)
                )

            else:
                self.log(
                    message=f"{self.log_type}: No events to forward. Waiting {self.frequency} seconds",
                    level="info",
                )
                time.sleep(self.frequency)

        except StopIteration:
            pass

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).observe(
            batch_duration
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.log_type}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self):
        self.log(
            message=f"Start fetching `{self.log_type}` logs from Trend Micro Email Security",
            level="info",
        )

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                traceback.print_exc()
                self.log_exception(error, message="Failed to forward events")


class TrendMicroEmailSecurityConnector(Connector):
    configuration: TrendMicroConnectorConfiguration
    module: TrendMicroModule

    WORKER_TYPES = ("accepted_traffic", "blocked_traffic")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

        self.consumers = {}

    def start_consumers(self) -> dict[str, TrendMicroWorker]:
        consumers = {}

        for consumer_name in self.WORKER_TYPES:
            self.log(message=f"Start `{consumer_name}` consumer", level="info")
            consumers[consumer_name] = TrendMicroWorker(connector=self, log_type=consumer_name)
            consumers[consumer_name].start()

        return consumers

    def supervise_consumers(self, consumers: dict[str, TrendMicroWorker]):
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting `{consumer_name}` consumer", level="info")

                consumers[consumer_name] = TrendMicroWorker(connector=self, log_type=consumer_name)
                consumers[consumer_name].start()

    def stop_consumers(self, consumers: dict[str, TrendMicroWorker]):
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping `{consumer_name}` consumer", level="info")
                consumer.stop()

    def run(self):
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
