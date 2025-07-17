import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from pydantic.v1 import Field
from requests import Response
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import VectraModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class VectraEntityScoringConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(60, description="Batch frequency in seconds")
    start_time: int = Field(1, description="The number of hours from which events should be queried")
    chunk_size: int = Field(500, description="The max size of chunks for the batch processing")


class VectraEntityScoringConsumer(Thread):
    def __init__(self, connector: "VectraEntityScoringConnector", entity_type: str, client: ApiClient) -> None:
        super().__init__()

        self.connector = connector
        self.configuration = self.connector.configuration
        self.entity_type = entity_type
        self.name = entity_type
        self.client = client

        self._stop_event = Event()

        self.cache_size = 1000
        self.events_cache: Cache = self.load_events_cache()
        self.cursor = CheckpointCursor(
            path=self.connector.data_path, lock=self.connector.context_lock, subkey=self.entity_type
        )

    @cached_property
    def base_url(self):
        base_url = self.connector.module.configuration.base_url.rstrip("/")

        if base_url.startswith("http://"):
            return f"https://{base_url[7:]}"

        if not base_url.startswith("https://"):
            return f"https://{base_url}"

        return base_url

    def log(self, *args, **kwargs) -> None:
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs) -> None:
        self.connector.log_exception(*args, **kwargs)

    @property
    def running(self) -> bool:
        return not self._stop_event.is_set()

    def stop(self) -> None:
        self._stop_event.set()

    # Used for backward compatibility with a previous connector version.
    # Cached because it's called just once for a check
    @cached_property
    def last_event_date(self) -> datetime | None:
        with self.connector.context as cache, self.connector.context_lock:
            most_recent_date_requested_str = cache.get(self.entity_type, {}).get("last_event_date")

        if most_recent_date_requested_str is None:
            return None

        most_recent_date_requested = isoparse(most_recent_date_requested_str)

        now = datetime.now(timezone.utc)
        one_month_ago = now - timedelta(days=30)
        if most_recent_date_requested < one_month_ago:
            most_recent_date_requested = one_month_ago

        return most_recent_date_requested

    def load_events_cache(self) -> Cache:
        cache: Cache = LRUCache(maxsize=self.cache_size)

        with self.connector.context_lock:
            with self.connector.cache_context as context:
                # load the cache from the context
                events_cache = context.get(self.entity_type, {}).get("events_cache", [])

        for event_hash in events_cache:
            cache[event_hash] = True

        return cache

    def update_cache(self):
        with self.connector.cache_context as cache, self.connector.context_lock:
            if self.entity_type not in cache:
                cache[self.entity_type] = {}

            cache[self.entity_type]["events_cache"] = list(self.events_cache.keys())

    def filter_processed_events(self, events: list[dict]) -> Generator[dict, None, None]:
        for event in events:
            event_id = event["id"]
            if event_id in self.events_cache:
                continue

            self.events_cache[event_id] = True
            yield event

    def __get_request(self, *args, **kwargs) -> Response:
        try:
            response = self.client.get(*args, **kwargs)
            response.raise_for_status()

            return response

        except requests.exceptions.HTTPError as err:
            level = "critical" if err.response.status_code in [401, 403] else "error"
            message = f"Request to Vectra API failed with status {err.response.status_code} - {err.response.reason}"

            try:
                raw = err.response.json()
                message = f"{message} - details: {raw['error']}"

            except Exception:
                pass

            self.log(message, level=level)
            raise

    def __fetch_next_events(self) -> Generator[list, None, None]:
        cursor_offset = self.cursor.offset
        last_event_datetime = self.last_event_date

        params = {"type": self.entity_type, "limit": self.connector.configuration.chunk_size}

        if cursor_offset is not None:
            # we have a new cursor
            params["from"] = cursor_offset

        elif cursor_offset is None and last_event_datetime is not None:
            # we have an old cursor
            params["event_timestamp_gte"] = last_event_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        else:
            # we have no cursor
            start_datetime = datetime.now() - timedelta(hours=self.configuration.start_time)
            params["event_timestamp_gte"] = start_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        url = f"{self.base_url}/api/v3.4/events/entity_scoring"
        response = self.__get_request(url, params=params)

        while self.running:
            raw = response.json()

            events = raw.get("events", [])
            next_checkpoint = raw["next_checkpoint"]

            if len(events) > 0:
                yield events
                self.cursor.offset = next_checkpoint

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.entity_type).set(0)
                return

            if raw["remaining_count"] == 0:
                return

            response = self.__get_request(
                url,
                params={
                    "type": self.entity_type,
                    "from": next_checkpoint,
                    "limit": self.connector.configuration.chunk_size,
                },
            )

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen: datetime | None = None

        for next_events in self.__fetch_next_events():
            if next_events:
                most_recent_date_seen = max(isoparse(item["event_timestamp"]) for item in next_events)

                # forward current events
                yield next_events

        if most_recent_date_seen:
            delta_time = (datetime.now(timezone.utc) - most_recent_date_seen).total_seconds()
            current_lag = int(delta_time)
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.entity_type).set(current_lag)

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, type=self.entity_type).inc(
                    len(batch_of_events)
                )
                self.connector.push_events_to_intakes(events=batch_of_events)

            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

            # Update cache of processed events
            self.update_cache()

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="info")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, type=self.entity_type).observe(
            batch_duration
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching Vectra Respond UX logs", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")


class VectraEntityScoringConnector(Connector):
    module: VectraModule
    configuration: VectraEntityScoringConnectorConfiguration

    ENTITY_TYPES = ("account", "host")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self.data_path)
        self.cache_context = PersistentJSON("cache.json", self.data_path)
        self.context_lock = Lock()
        self.consumers: dict[str, VectraEntityScoringConsumer] = {}

    def start_consumers(self, client: ApiClient) -> dict[str, VectraEntityScoringConsumer]:
        consumers = {}
        for entity_type in self.ENTITY_TYPES:
            self.log(message=f"Start {entity_type} consumer", level="info")
            consumers[entity_type] = VectraEntityScoringConsumer(
                connector=self, entity_type=entity_type, client=client
            )
            consumers[entity_type].start()

        return consumers

    def supervise_consumers(self, consumers: dict[str, VectraEntityScoringConsumer], client: ApiClient) -> None:
        for entity_type, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {entity_type} consumer", level="info")

                consumers[entity_type] = VectraEntityScoringConsumer(
                    connector=self, entity_type=entity_type, client=client
                )
                consumers[entity_type].start()

    def stop_consumers(self, consumers: dict[str, VectraEntityScoringConsumer]) -> None:
        for entity_type, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {entity_type} consumer", level="info")
                consumer.stop()

    def run(self):
        client = ApiClient(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            ratelimit_per_second=4,
        )

        consumers = self.start_consumers(client)

        while self.running:
            self.supervise_consumers(consumers, client)
            time.sleep(5)

        self.stop_consumers(consumers)
