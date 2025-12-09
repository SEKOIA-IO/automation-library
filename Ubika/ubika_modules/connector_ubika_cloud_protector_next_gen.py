import time
from codecs import replace_errors
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import UbikaModule
from .client import UbikaCloudProtectorNextGenApiClient
from .client.auth import AuthorizationError
from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from .timestepper import TimeStepper


class FetchEventsException(Exception):
    pass


class UbikaCloudProtectorNextGenConnectorConfiguration(DefaultConnectorConfiguration):
    namespace: str = Field(..., description="Namespace")
    refresh_token: str = Field(..., description="API refresh token", secret=True)

    frequency: int = 60
    chunk_size: int = 1000
    # Time stepper settings
    timedelta: int = 1
    start_time: int = 1


class UbikaCloudProtectorNextGenConnector(Connector):
    module: UbikaModule
    configuration: UbikaCloudProtectorNextGenConnectorConfiguration

    NAME = "Ubika Cloud Protector Next"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            path=self.data_path,
            time_unit=TimeUnit.MILLISECOND,
            start_at=timedelta(days=30),
            ignore_older_than=timedelta(days=60),
        )
        self.from_timestamp = self.cursor.offset

        self.context = PersistentJSON("context.json", self.data_path)
        self.cache_context = PersistentJSON("cache.json", self.data_path)
        self.cache_size = 1000
        self.events_cache: Cache = self.load_events_cache()

    @cached_property
    def stepper(self):
        # Read the most recent date seen from the context
        with self.context as cache:
            most_recent_date_str = cache.get("most_recent_date_seen")

            # if not defined, create a new time stepper from the configuration
            if most_recent_date_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            # parse the most recent requested date
            most_recent_date = isoparse(most_recent_date_str)

            # Ensure we don't go back more than one month
            now = datetime.now(UTC)
            one_month_ago = now - timedelta(days=30)
            # if the most recent date is older than one month, set it to one month ago
            if most_recent_date < one_month_ago:
                most_recent_date = one_month_ago

            # create a time stepper from the most recent date seen
            return TimeStepper.create_from_time(
                self,
                most_recent_date,
                self.configuration.frequency,
                self.configuration.timedelta,
            )

    def load_events_cache(self) -> Cache:
        """
        Load the events cache.
        """
        cache: Cache = LRUCache(maxsize=self.cache_size)

        with self.cache_context as context:
            # load the cache from the context
            events_cache = context.get("events_cache", [])

        for event_hash in events_cache:
            cache[event_hash] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Save the events cache.
        """
        with self.cache_context as context:
            # save the events cache to the context
            context["events_cache"] = list(self.events_cache.keys())

    def filter_processed_events(self, events: list[dict]) -> list[dict]:
        """
        Filter out events that have already been processed
        """
        filtered_events = []

        # Use a cache to store the hashes of processed events
        for event in events:
            event_id = event["logAlertUid"]

            # Check if the event id is already in the cache
            if event_id not in self.events_cache:
                # If not, add the event to the filtered list
                filtered_events.append(event)

                # Add the event id to the cache
                self.events_cache[event_id] = True

        return filtered_events

    @cached_property
    def client(self) -> UbikaCloudProtectorNextGenApiClient:
        return UbikaCloudProtectorNextGenApiClient(refresh_token=self.configuration.refresh_token)

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = (
                f"Request on {self.NAME} API to fetch events failed with status "
                f"{response.status_code} - {response.reason} on {response.request.url}"
            )

            raise FetchEventsException(message)

    def __fetch_next_events(
        self, start_timestamp: int, end_timestamp: int
    ) -> Generator[list[dict[str, Any]], None, None]:
        # get the first page of events
        headers = {"Content-Type": "application/json"}
        url = f"https://api.ubika.io/rest/logs.ubika.io/v1/ns/{self.configuration.namespace}/security-events"
        params = {
            "filters.fromDate": start_timestamp,
            "filters.toDate": end_timestamp,
            "pagination.realtime": True,
            "pagination.pageSize": self.configuration.chunk_size,
        }

        try:
            response = self.client.get(url, params=params, headers=headers, timeout=60)

        except AuthorizationError as err:
            self.log(f"Authorization error: {err.args[1]}", level="critical")
            raise

        while self.running:
            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            data = response.json()

            events = data.get("spec", {}).get("items", [])

            # yielding events if defined
            if len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                yield events

            else:
                self.log(
                    message="The last page of events was empty.",
                    level="info",
                )  # pragma: no cover
                return

            cursor = data.get("spec", {}).get("nextPageToken")
            if cursor is None:
                return

            try:
                response = self.client.get(
                    url,
                    params={
                        "pagination.pageToken": cursor,
                        "pagination.pageSize": self.configuration.chunk_size,
                        "pagination.realtime": True,
                    },
                    headers=headers,
                    timeout=60,
                )

            except AuthorizationError as err:
                self.log(f"Authorization error: {err.args[1] if len(err.args)>1 else str(err)}", level="critical")
                raise

    def next_batch(self, start: datetime, end: datetime) -> None:
        # save the starting time
        batch_start_time = time.time()
        start_timestamp = int(start.timestamp() * 1000)
        end_timestamp = int(end.timestamp() * 1000)

        # Fetch next batch
        for events in self.__fetch_next_events(start_timestamp, end_timestamp):
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in self.filter_processed_events(events)]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )  # pragma: no cover
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )  # pragma: no cover

        # just in case
        self.save_events_cache()

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )  # pragma: no cover
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

    def run(self) -> None:
        self.log(message=f"Start fetching {self.NAME} events", level="info")  # pragma: no cover

        for start, end in self.stepper.ranges():
            # Check if we need to stop
            if self._stop_event.is_set():
                break

            try:
                self.next_batch(start, end)
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")  # pragma: no cover
            finally:
                with self.context as cache:
                    cache["most_recent_date_seen"] = end.isoformat()

        self.save_events_cache()
