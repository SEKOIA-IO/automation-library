import time
from datetime import datetime

import orjson
from cachetools import Cache, LRUCache
from sekoia_automation.storage import PersistentJSON

from .connector_ubika_cloud_protector_next_gen_base import (
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class UbikaCloudProtectorNextGenConnectorConfiguration(UbikaCloudProtectorNextGenBaseConnectorConfiguration):
    pass


class UbikaCloudProtectorNextGenConnector(UbikaCloudProtectorNextGenBaseConnector):
    NAME: str = "Ubika Cloud Protector Next"
    configuration: UbikaCloudProtectorNextGenConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_context = PersistentJSON("cache.json", self.data_path)
        self.cache_size = 1000
        self.events_cache: Cache = self.load_events_cache()

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

    def next_batch(self, start: datetime, end: datetime) -> None:
        # save the starting time
        batch_start_time = time.time()
        start_timestamp = int(start.timestamp() * 1000)
        end_timestamp = int(end.timestamp() * 1000)

        # Fetch next batch
        for events in self._get_pages(
            endpoint="security-events",
            params={
                "filters.fromDate": start_timestamp,
                "filters.toDate": end_timestamp,
                "pagination.realtime": True,
                "pagination.pageSize": self.configuration.chunk_size,
            },
        ):
            filtered_events = self.filter_processed_events(events)
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in filtered_events]

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

        with self.context as cache:
            cache["most_recent_date_seen"] = end.isoformat()

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
                break

        # Close the client connection
        self.client.close()

        self.save_events_cache()
