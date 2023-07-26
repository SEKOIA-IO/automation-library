import time
from datetime import datetime
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Any, Generator

import orjson
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import VadeCloudModule
from .client import ApiClient
from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FetchEventException(Exception):
    pass


class VadeCloudConsumer(Thread):
    def __init__(
        self,
        connector: "VadeCloudLogsConnector",
        name: str,
        params: dict[str, Any] | None = None,
    ):
        super().__init__()

        self.connector = connector
        self.params = params or {}
        self.name = name
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def get_last_timestamp(self) -> int:
        now = int(time.time() * 1000)  # in milliseconds

        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_ts_seen = cache.get("last_ts")

            # if undefined, retrieve events from the last 5 minutes
            if most_recent_ts_seen is None:
                return now - 5 * 60 * 1000

            # We don't retrieve messages older than one week
            one_week_ago = now - 7 * 24 * 60 * 60 * 1000
            if most_recent_ts_seen < one_week_ago:
                most_recent_ts_seen = one_week_ago
        self.connector.context_lock.release()

        return most_recent_ts_seen

    def set_last_timestamp(self, last_timestamp: int) -> None:
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            cache["last_ts"] = last_timestamp

        self.connector.context_lock.release()

    @cached_property
    def client(self):
        return ApiClient(
            self.connector.module.configuration.hostname,
            self.connector.module.configuration.login,
            self.connector.module.configuration.password,
            ratelimit_per_minute=self.connector.configuration.ratelimit_per_minute,
        )

    def request_logs_page(self, start_date: int, period: str, page: int = 0):
        params = {
            "userId": self.client.account_id,
            "pageSize": self.connector.configuration.chunk_size,
            "pageToGet": page,
            # "streamType": "Inbound",
            "period": period,
            "startDate": start_date,
        }
        params.update(self.params)  # override with custom stuff

        response = self.client.post(
            f"{self.connector.module.configuration.hostname}/rest/v3.0/filteringlog/getReport",
            json=params,
        )
        return response

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = f"Request on Vade Cloud API to fetch `{self.name}` logs failed with status {response.status_code} - {response.reason}"

            try:
                error = response.json()
                message = f"{message}: {error['error']}"

            except Exception:
                pass

            raise FetchEventException(message)

    def iterate_through_pages(self, from_timestamp: int) -> Generator[list, None, None]:
        page_num = 0
        search_period = "DAYS_07"  # long period will allow us to capture events with big time gap between them
        response = self.request_logs_page(start_date=from_timestamp, period=search_period, page=page_num)
        self._handle_response_error(response)

        while self.running:
            events = response.json().get("logs", [])

            if len(events) > 0:
                yield events
                page_num += 1

            else:
                return

            response = self.request_logs_page(start_date=from_timestamp, period=search_period, page=page_num)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_timestamp_seen = self.get_last_timestamp()

        for next_events in self.iterate_through_pages(most_recent_timestamp_seen):
            if next_events:
                # get the greater date seen in this list of events

                last_event = max(next_events, key=lambda x: x.get("date"))
                last_event_timestamp = last_event.get("date")

                self.log(
                    message=f"{self.name}: Last event timestamp is {last_event_timestamp} which is "
                    f"{datetime.fromtimestamp(last_event_timestamp // 1000).isoformat()}",
                    level="debug",
                )

                # save the greater date ever seen
                if last_event_timestamp > most_recent_timestamp_seen:
                    most_recent_timestamp_seen = last_event_timestamp + 1000

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_timestamp_seen > self.get_last_timestamp():
            self.set_last_timestamp(most_recent_timestamp_seen)

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"{self.name}: Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )

                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(batch_of_events)
                )

                self.connector.push_events_to_intakes(events=batch_of_events)

                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(events)
                )

            else:
                self.log(
                    message="{self.name}: No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.name).observe(
            batch_duration
        )

        self.log(
            message=f"{self.name}: Fetched and forwarded events in {batch_duration} seconds",
            level="info",
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.name}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self):
        try:
            while self.running:
                self.next_batch()

        except Exception as error:
            self.connector.log_exception(error, message=f"{self.name}: Failed to forward events")


class VadeCloudConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000
    ratelimit_per_minute: int = 20


class VadeCloudLogsConnector(Connector):
    configuration: VadeCloudConnectorConfiguration
    module: VadeCloudModule

    all_params = {
        "inbound": {"streamType": "Inbound"},
        "outbound": {"streamType": "Outbound"},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()
        self.consumers = {}

    def start_consumers(self):
        consumers = {}

        for consumer_name, params in self.all_params.items():
            self.log(message=f"Start `{consumer_name}` consumer", level="info")
            consumers[consumer_name] = VadeCloudConsumer(connector=self, name=consumer_name, params=params)
            consumers[consumer_name].start()

        return consumers

    def supervise_consumers(self, consumers):
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting `{consumer_name}` consumer", level="info")

                consumers[consumer_name] = VadeCloudConsumer(
                    connector=self,
                    name=consumer_name,
                    params=self.all_params.get(consumer_name),
                )
                consumers[consumer_name].start()

    def stop_consumers(self, consumers):
        for name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping `{name}` consumer", level="info")
                consumer.stop()

    def run(self):
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
