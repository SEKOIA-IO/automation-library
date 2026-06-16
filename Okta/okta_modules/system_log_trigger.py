import hashlib
import signal
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from posixpath import join as urljoin
from threading import Event
from typing import Any, Optional

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from okta_modules import OktaModule
from okta_modules.client import ApiClient
from okta_modules.helpers import get_upper_second
from okta_modules.logging import get_logger
from okta_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class FetchEventsException(Exception):
    pass


def compute_event_checksum(event: dict[str, Any]) -> str:
    """
    Compute a checksum of event content to detect duplicates even if UUID is missing.
    Uses key fields that uniquely identify an event occurrence.
    """
    target = event.get("target")
    target_id = None
    if isinstance(target, dict):
        target_id = target.get("id")
    elif isinstance(target, list) and target:
        first_target = target[0]
        if isinstance(first_target, dict):
            target_id = first_target.get("id")

    event_hash_input = {
        "eventType": event.get("eventType"),
        "published": event.get("published"),
        "actor_id": event.get("actor", {}).get("id"),
        "target_id": target_id,
    }

    event_json = orjson.dumps(event_hash_input, default=str)
    return hashlib.sha256(event_json).hexdigest()


class SystemLogConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    ratelimit_per_minute: int = 20
    filter: str | None = None
    q: str | None = None


class SystemLogConnector(Connector):
    """
    This connector fetches system logs from Okta API
    """

    module: OktaModule
    configuration: SystemLogConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)
        self.fetch_events_limit = 1000

        self.cursor = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(minutes=1),
            ignore_older_than=timedelta(days=7),
        )

        self.cache_size = 2000
        self.events_cache: Cache[str, bool] = self.load_events_cache()

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def load_events_cache(self) -> Cache[str, bool]:
        """
        Load the events cache from persistent storage.
        Cache stores both UUIDs and event checksums for robust deduplication.
        """
        cache: Cache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            # load the cache from the context - includes both UUIDs and checksums
            events_cache = context.get("events_cache", [])

        for cache_key in events_cache:
            cache[cache_key] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Persist the events cache to disk.
        Stores both UUIDs and checksums for robust deduplication across restarts.
        """
        with self.context as context:
            # save the events cache to the context - includes both UUIDs and checksums
            context["events_cache"] = list(self.events_cache.keys())

    def exit(self, _: Any, __: Optional[Any]) -> None:
        self.log(message="Stopping OKTA system logs connector", level="info")
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            apikey=self.module.configuration.apikey,
            ratelimit_per_minute=self.configuration.ratelimit_per_minute,
        )

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = (
                f"Request on Okta API to fetch events failed with status {response.status_code} - {response.reason}"
            )

            # enrich error logs with detail from the Okta API
            try:
                error = response.json()
                message = f"{message}: {error['errorCode']} - {error['errorSummary']}"
            except Exception:
                pass

            raise FetchEventsException(message)

    def __fetch_next_events(self, from_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        # set parameters
        params: dict[str, str | int] = {
            "since": from_date.isoformat(),
            "limit": self.fetch_events_limit,
            "sortOrder": "ASCENDING",
        }

        # add optional parameters
        for param_name in ("filter", "q"):
            value = getattr(self.configuration, param_name)

            if value is not None:
                params[param_name] = value

        # get the first page of events
        headers = {"Accept": "application/json"}
        url = urljoin(self.module.configuration.base_url, "api/v1/logs")

        params_to_use: None | dict[str, str | int] = params

        while url is not None and not self._stop_event.is_set():
            response = self.client.get(url, params=params_to_use, headers=headers)

            params_to_use = None

            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            events = response.json()

            # Filter events that have already been processed.
            # Prefer UUID when available, fallback to checksum otherwise.
            filtered_events = []
            for event in events:
                event_uuid = event.get("uuid")
                if event_uuid is not None:
                    if event_uuid not in self.events_cache:
                        filtered_events.append(event)
                else:
                    event_checksum = compute_event_checksum(event)
                    if event_checksum not in self.events_cache:
                        filtered_events.append(event)

            # Only include events that are not present in cache.
            if filtered_events:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(filtered_events))

                yield filtered_events
            else:
                logger.info(
                    f"The last page of events was empty. Waiting {self.configuration.frequency}s "
                    "before fetching next page"
                )
                time.sleep(self.configuration.frequency)

            url = response.links.get("next", {}).get("url")

            if url is None:
                return

    def _compute_batch_checkpoint(self, events: list[dict[str, Any]]) -> datetime | None:
        events_date: list[str] = sorted(x["published"] for x in events if x.get("published") is not None)
        if len(events_date) == 0:
            return None

        return get_upper_second(isoparse(events_date[-1]))

    def _update_checkpoint(self, events: list[dict[str, Any]]) -> None:
        next_checkpoint = self._compute_batch_checkpoint(events)
        if next_checkpoint is not None and next_checkpoint > self.cursor.offset:
            self.cursor.offset = next_checkpoint

    def fetch_events(self) -> Generator[list[dict[str, Any]], None, None]:
        from_date = self.cursor.offset

        for next_events in self.__fetch_next_events(from_date):
            if next_events:
                yield next_events

        now = datetime.now(timezone.utc)
        current_lag = now - self.cursor.offset
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            pushed_events = events
            serialized_events = [orjson.dumps(event).decode("utf-8") for event in pushed_events]

            # if the batch is full, push it
            if len(serialized_events) > 0:
                # Update cache BEFORE pushing events (better atomicity)
                # This prevents duplicates if process crashes during/after push
                for event in pushed_events:
                    event_uuid = event.get("uuid")

                    # Cache UUID when available to maximize LRU coverage.
                    if event_uuid is not None:
                        self.events_cache[event_uuid] = True
                    else:
                        event_checksum = compute_event_checksum(event)
                        self.events_cache[event_checksum] = True

                # Persist cache to disk before pushing events
                self.save_events_cache()

                self.log(
                    message=f"Forwarded {len(serialized_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(serialized_events))
                self.push_events_to_intakes(events=serialized_events)

                # Advance checkpoint only after successful push.
                # This prevents replay storms on restart while keeping at-least-once delivery semantics.
                self._update_checkpoint(pushed_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching OKTA system logs", level="info")

        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
