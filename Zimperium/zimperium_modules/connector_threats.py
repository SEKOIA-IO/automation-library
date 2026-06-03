import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from posixpath import join as urljoin
from typing import Any, Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import ZimperiumModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class MobileThreatDefenceConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class MobileThreatDefenceConnector(Connector):
    module: ZimperiumModule
    configuration: MobileThreatDefenceConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self.data_path)
        self.cursor = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=200),
            ignore_older_than=timedelta(days=300),
        )

        self.cache_size = 2000
        self.events_cache: Cache = self.load_events_cache()

    def load_events_cache(self) -> Cache:
        """
        Load the events cache.
        """
        cache: Cache = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            # load the cache from the context
            events_cache = context.get("events_cache", [])

        for uuid in events_cache:
            cache[uuid] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Save the events cache.
        """
        with self.context as context:
            # save the events cache to the context
            context["events_cache"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    def handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Zimperium MTD API to fetch events failed with status {response.status_code} - {response.reason}"

            # enrich error logs with detail from the Zimperium MTD API
            try:
                error = response.json()
                message = f"{message}: {error['detail']}"

            except Exception:
                pass

            self.log(message, level="error")
            response.raise_for_status()

    def __fetch_next_events(self, from_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        page_num = 0

        headers = {"Accept": "application/json"}
        url = urljoin(self.module.configuration.base_url, "api/threats/public/v1/threats")
        params: dict[str, str | int] = {
            "module": "ZIPS",
            "after": from_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page": page_num,
            "size": self.configuration.chunk_size,
            "sort": "timestamp,asc",
        }

        while True:
            response = self.client.get(url, params=params, headers=headers)
            self.handle_response_error(response)

            raw = response.json()
            events = raw.get("content", [])

            if len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                yield events

            else:
                self.log("Last page was empty. Waiting for the next batch", level="info")
                return

            if raw["last"] is True:
                return

            page_num += 1
            params["page"] = page_num

    def fetch_events(self) -> Generator[list[dict[str, Any]], None, None]:
        most_recent_date_seen = self.cursor.offset

        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    last_event_timestamp = max(
                        item["timestamp"] // 1000 for item in next_events if item.get("timestamp") is not None
                    )
                    last_event_date = datetime.fromtimestamp(last_event_timestamp, tz=timezone.utc)

                    if last_event_date > most_recent_date_seen:
                        most_recent_date_seen = last_event_date

                    yield next_events

        finally:
            if most_recent_date_seen > self.cursor.offset:
                self.cursor.offset = most_recent_date_seen

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [
                orjson.dumps(event).decode("utf-8") for event in events if event["id"] not in self.events_cache
            ]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)

                # Persist cache of event UUIDs after pushing to intake
                for event in events:
                    self.events_cache[event["id"]] = True

                self.save_events_cache()
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="info")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching Zimperium MTD Threats events", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
