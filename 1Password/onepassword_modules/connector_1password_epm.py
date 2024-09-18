import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Any, Generator
from urllib.parse import urljoin

import orjson
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import OnePasswordModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class OnePasswordConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class OnePasswordEndpoint(Thread):
    METHOD_URI: str
    FEATURE_NAME: str

    def __init__(self, connector: "OnePasswordConnector") -> None:
        super().__init__()
        self._stop_event = Event()
        self.name = self.FEATURE_NAME

        self.connector = connector
        self.cursor = self.load_cursor()

    def log(self, *args, **kwargs) -> None:
        self.connector.log(*args, **kwargs)

    def load_cursor(self) -> str | None:
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_cursor_seen = cache.get(self.FEATURE_NAME, {}).get("most_recent_cursor_seen")
        self.connector.context_lock.release()

        return most_recent_cursor_seen

    def save_cursor(self, cursor: str | None) -> None:
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            if self.FEATURE_NAME not in cache:
                cache[self.FEATURE_NAME] = {"most_recent_cursor_seen": cursor}
            else:
                cache[self.FEATURE_NAME]["most_recent_cursor_seen"] = cursor
        self.connector.context_lock.release()

    @property
    def running(self) -> bool:
        return not self._stop_event.is_set()

    def stop(self) -> None:
        self._stop_event.set()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(api_token=self.connector.module.configuration.api_token)

    def enrich_event(self, event: dict) -> dict:
        # adding field to distinguish different types of event in Sekoia
        event["sekoia_event_type"] = self.FEATURE_NAME
        return event

    def extract_timestamp(self, event: dict) -> datetime:
        return isoparse(event["timestamp"])

    def fetch_page(self, cursor: str | None) -> dict[str, Any]:
        url = urljoin(self.connector.base_url, self.METHOD_URI)
        end_datetime = datetime.now().astimezone(timezone.utc).replace(microsecond=0)
        start_datetime = end_datetime - timedelta(days=30)

        data: dict[str, str | int] = {}
        if cursor:
            data["cursor"] = cursor

        else:
            data["limit"] = self.connector.configuration.chunk_size
            data["start_time"] = start_datetime.isoformat()
            data["end_time"] = end_datetime.isoformat()

        response = self.client.post(url, json=data)
        return response.json()

    def fetch_events(self) -> Generator[list, None, None]:
        page = self.fetch_page(cursor=self.cursor)

        while self.running:
            events = page.get("items", [])
            self.cursor = page["cursor"]

            if len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(events)
                )
                last_event = max(events, key=self.extract_timestamp)
                last_event_datetime = self.extract_timestamp(last_event)

                current_lag = int((datetime.now().astimezone(timezone.utc) - last_event_datetime).total_seconds())
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.name).set(current_lag)
                yield events

            else:
                self.save_cursor(cursor=self.cursor)
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.name).set(0)
                return

            if not page.get("has_more"):
                self.save_cursor(cursor=self.cursor)
                EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.name).set(0)
                return

            page = self.fetch_page(cursor=self.cursor)

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(self.enrich_event(event)).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.name).inc(
                    len(batch_of_events)
                )
                self.connector.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        # get the ending time and compute the duration to fetch the events
        batch_duration = int(batch_end_time - batch_start_time)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.name).observe(
            batch_duration
        )

        self.log(
            message=f"{self.name}: Fetched and forwarded events in {batch_duration} seconds",
            level="info",
        )
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.name}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )

            time.sleep(delta_sleep)

    def run(self) -> None:  # pragma: no cover
        try:
            while self.running:
                self.next_batch()

        except Exception as error:
            self.connector.log_exception(error, message=f"{self.name}: Failed to forward events")


class SignInAttemptsEndpoint(OnePasswordEndpoint):
    METHOD_URI = "/api/v1/signinattempts"
    FEATURE_NAME = "signinattempts"


class ItemUsagesEndpoint(OnePasswordEndpoint):
    METHOD_URI = "/api/v1/itemusages"
    FEATURE_NAME = "itemusages"


class AuditEventsEndpoint(OnePasswordEndpoint):
    METHOD_URI = "/api/v1/auditevents"
    FEATURE_NAME = "auditevents"


class OnePasswordConnector(Connector):
    module: OnePasswordModule
    configuration: OnePasswordConnectorConfiguration

    FEATURE_TO_CLASS = {
        SignInAttemptsEndpoint.FEATURE_NAME: SignInAttemptsEndpoint,
        ItemUsagesEndpoint.FEATURE_NAME: ItemUsagesEndpoint,
        AuditEventsEndpoint.FEATURE_NAME: AuditEventsEndpoint,
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

        self.base_url = self.module.configuration.base_url

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(api_token=self.module.configuration.api_token)

    @cached_property
    def get_allowed_endpoints(self) -> list:
        url = urljoin(self.base_url, "/api/v2/auth/introspect")
        response = self.client.get(url)
        allowed_endpoints = response.json().get("features", [])
        return allowed_endpoints

    def start_consumers(self) -> dict[str, OnePasswordEndpoint]:
        consumers = {}

        for consumer_name in self.get_allowed_endpoints:
            self.log(message=f"Start `{consumer_name}` consumer", level="info")

            cls = self.FEATURE_TO_CLASS[consumer_name]
            consumers[consumer_name] = cls(connector=self)
            consumers[consumer_name].start()

        return consumers

    def stop_consumers(self, consumers: dict[str, OnePasswordEndpoint]) -> None:
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stop consuming `{consumer_name}` logs", level="info")
                consumer.stop()

    def supervise_consumers(self, consumers: dict[str, OnePasswordEndpoint]) -> None:
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restart consuming `{consumer_name}` logs", level="info")

                cls = self.FEATURE_TO_CLASS[consumer_name]
                consumers[consumer_name] = cls(connector=self)
                consumers[consumer_name].start()

    def run(self) -> None:
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
