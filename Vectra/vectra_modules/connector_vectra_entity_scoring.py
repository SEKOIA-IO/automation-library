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
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import VectraModule
from .client import ApiClient
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from .timestepper import TimeStepper


class VectraEntityScoringConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(60, description="Batch frequency in seconds")
    timedelta: int = Field(
        0, description="The temporal shift, in the past, in minutes, the connector applies when fetching the events"
    )
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

    @property
    def stepper(self) -> TimeStepper:
        with self.connector.context as cache, self.connector.context_lock:
            most_recent_date_requested_str = cache.get(self.entity_type, {}).get("last_event_date")

        if most_recent_date_requested_str is None:
            return TimeStepper.create(
                self,
                self.configuration.frequency,
                self.configuration.timedelta,
                self.configuration.start_time,
            )

        # parse the most recent requested date
        most_recent_date_requested = isoparse(most_recent_date_requested_str)

        now = datetime.now(timezone.utc)
        one_month_ago = now - timedelta(days=30)
        if most_recent_date_requested < one_month_ago:
            most_recent_date_requested = one_month_ago

        return TimeStepper.create_from_time(
            self,
            most_recent_date_requested,
            self.configuration.frequency,
            self.configuration.timedelta,
        )

    def update_stepper(self, new_datetime: datetime) -> None:
        with self.connector.context as cache, self.connector.context_lock:
            if self.entity_type not in cache:
                cache[self.entity_type] = {}

            cache[self.entity_type]["last_event_date"] = new_datetime.isoformat()

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
                message = raw["error"]

            except Exception:
                pass

            self.log(message, level=level)
            raise

    def fetch_events(self, start_datetime: datetime, end_datetime: datetime):
        formatted_start_date = start_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        formatted_end_date = end_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        url = f"{self.base_url}/api/v3.4/events/entity_scoring"
        response = self.__get_request(
            url,
            params={
                "type": self.entity_type,
                "event_timestamp_gte": formatted_start_date,
                "event_timestamp_lte": formatted_end_date,
                "limit": self.connector.configuration.chunk_size,
            },
        )

        while self.running:
            raw = response.json()

            events = raw.get("events", [])
            if len(events) > 0:
                yield events

            else:
                return

            if raw["remaining_count"] == 0:
                return

            next_checkpoint = raw["next_checkpoint"]
            response = self.__get_request(
                url,
                params={
                    "type": self.entity_type,
                    "from": next_checkpoint,
                    "event_timestamp_gte": formatted_start_date,
                    "event_timestamp_lte": formatted_end_date,
                    "limit": self.connector.configuration.chunk_size,
                },
            )

    def run(self) -> None:
        for start, end in self.stepper.ranges():
            if not self.running:
                break

            duration_start = time.time()

            list_of_events = self.fetch_events(start_datetime=start, end_datetime=end)
            events = [event for batch in list_of_events for event in batch]
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]

            if len(batch_of_events) > 0:
                self.log("Forwarded %d events" % len(batch_of_events), level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, type=self.entity_type).inc(
                    len(batch_of_events)
                )
                self.connector.push_events_to_intakes(batch_of_events)

            else:
                self.log("No events forwarded", level="info")

            # Update last datetime
            self.update_stepper(end)
            self.update_cache()

            duration = int(time.time() - duration_start)
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, type=self.entity_type).observe(
                duration
            )


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
