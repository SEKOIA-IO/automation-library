import signal
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from threading import Event
from typing import Any
from urllib.parse import urljoin

import httpx
import orjson
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import UbikaModule
from .client import UbikaCloudProtectorNextGenApiClient
from .client.auth import AuthorizationError, AuthorizationTimeoutError
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FetchEventsException(Exception):
    """Raised on non-2xx responses from the Ubika API."""


class UbikaCloudProtectorNextGenBaseConnectorConfiguration(DefaultConnectorConfiguration):
    """
    Common configuration for all NextGen connectors.
    """

    namespace: str = Field(..., description="Namespace")
    refresh_token: str = Field(..., description="Refresh API token", secret=True)

    base_url: str = Field("https://api.ubika.io/", description="API base URL")
    frequency: int = Field(60, description="Batch frequency in seconds", ge=1)
    chunk_size: int = Field(1000, description="The size of chunks for the batch processing", ge=1)
    start_time: int = Field(1, description="The number of hours from which events should be queried", ge=0)


class UbikaCloudProtectorNextGenBaseConnector(Connector):
    """
    Base class for Next-Gen connectors.

    Uses a single ``filters.fromDate`` timestamp cursor as checkpoint:
      • read the most recent event timestamp from ``context.json`` on startup
      • page through the API with ``nextPageToken`` until the items list is empty
      • forward the events and persist the greatest timestamp seen (per page, then +1ms)
      • sleep ``frequency`` seconds between batches

    Checkpointing is per page so a crash replays at most one page; an LRU cache of
    event ids then deduplicates the replayed (or ``realtime``-resurfaced) events.
    """

    module: UbikaModule

    NAME: str = "Ubika Cloud Protector NextGen Base"
    configuration: UbikaCloudProtectorNextGenBaseConnectorConfiguration

    cache_size: int = 1000  # Default cache size, can be overridden in subclasses
    endpoint: str = ""  # Must be set by subclasses (e.g., "security-events", "traffic-logs")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        # Single file to store our checkpoint
        self.context = PersistentJSON("context.json", self.data_path)
        # Cache context for storing event hashes
        self.cache_context = PersistentJSON("cache.json", self.data_path)
        self.events_cache: Cache = self.load_events_cache()
        # HTTP client for API requests (lazily initialized)
        self._client: UbikaCloudProtectorNextGenApiClient | None = None

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, _: Any, __: Any) -> None:
        self.log(message=f"Stopping {self.NAME} connector", level="info")
        self._stop_event.set()

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

    @property
    def client(self) -> UbikaCloudProtectorNextGenApiClient:
        """
        HTTP client that automatically injects tokens and handles rate‐limits.
        Lazily initialized on first access; use _client to manage lifecycle.
        """
        if self._client is None:
            self._client = UbikaCloudProtectorNextGenApiClient(refresh_token=self.configuration.refresh_token)
        return self._client

    @property
    def most_recent_timestamp_seen(self) -> int:
        """
        Return the checkpoint, in epoch milliseconds, to use as ``filters.fromDate``.

        Reads ``most_recent_timestamp_seen`` (epoch ms) from the context, falling back
        to the legacy ``most_recent_date_seen`` (ISO 8601) for upgrade continuity. If
        neither is defined, backfills ``start_time`` hours. The checkpoint is never
        older than one week.
        """
        now = datetime.now(UTC)

        with self.context as cache:
            most_recent = cache.get("most_recent_timestamp_seen")
            legacy_date = cache.get("most_recent_date_seen")

        if most_recent is not None:
            most_recent_date = datetime.fromtimestamp(most_recent / 1000, tz=UTC)
        elif legacy_date is not None:
            most_recent_date = isoparse(legacy_date)
        elif self.configuration.start_time == 0:
            most_recent_date = now
        else:
            most_recent_date = now - timedelta(hours=self.configuration.start_time)

        # we don't retrieve events older than one week
        one_week_ago = now - timedelta(days=7)
        if most_recent_date < one_week_ago:
            most_recent_date = one_week_ago

        return int(most_recent_date.timestamp() * 1000)

    def _handle_response_error(self, response: httpx.Response) -> None:
        if not response.is_success:
            try:
                error_data = response.json()
                message = (
                    f"Request on {self.NAME} API to fetch events failed with status "
                    f"{response.status_code} - {error_data} on {response.request.url}"
                )
            except (ValueError, KeyError):
                message = (
                    f"Request on {self.NAME} API to fetch events failed with status "
                    f"{response.status_code} - {response.text} on {response.request.url}"
                )
            raise FetchEventsException(message)

    def _get_pages(self, endpoint: str, params: dict[str, Any]) -> Generator[list[dict], None, None]:
        """
        Generic paginator against the Ubika NextGen API.

        Args:
            endpoint: path under /v1/ns/{namespace}/…  (e.g. "security-events" or "traffic-logs")
            params: filters, e.g. {"filters.fromDate": 12345}

        Yields:
            one page = list of dicts under spec.items
        """
        # Build URL using the configured namespace
        # Guarantee the overall prefix ends in a slash so join() can drop extra slashes but never smash paths
        prefix = self.configuration.base_url.rstrip("/") + "/"
        path = f"rest/logs.ubika.io/v1/ns/{self.configuration.namespace}/{endpoint}"
        url = urljoin(prefix, path)
        headers = {"Content-Type": "application/json"}

        # First request using UbikaCloudProtectorNextGenApiClient
        response = self._safe_get_page(url=url, params=params, headers=headers, initial=True)

        # Loop until the connector is asked to stop
        while not self._stop_event.is_set():
            # Centralized HTTP error handling
            self._handle_response_error(response)

            # Parse the HTTP response body into a Python dict
            payload = response.json()

            # Extract events from the 'spec.items' field
            items = payload.get("spec", {}).get("items", [])
            if not items:
                # Stop when the list of events is empty
                self.log(message="The last page of events was empty.", level="info")
                return

            # Yield the current batch of items
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(items))
            yield items

            # Look for a nextPageToken to fetch further pages
            # A nextPageToken is an opaque cursor used to fetch the next page of results
            # An opaque cursor is a pagination token whose internal contents are hidden
            # and must be passed back verbatim
            token = payload.get("spec", {}).get("nextPageToken")
            if not token:
                # No more pages, end generator
                return

            # Fetch the next page using the pageToken
            response = self._safe_get_page(
                url=url,
                params={
                    "pagination.pageToken": token,
                    "pagination.pageSize": self.configuration.chunk_size,
                    "pagination.realtime": True,
                },
                headers=headers,
                initial=False,
            )

    def _safe_get_page(self, url: str, *, params, headers, initial: bool) -> httpx.Response:
        """
        Wrap client.get and centralize the AuthorizationError / Timeout logging.
        initial=True means "on initial fetch", otherwise "on next page".
        """
        phase = "initial fetch" if initial else "next page"
        try:
            return self.client.get(url, params=params, headers=headers, timeout=60)

        except AuthorizationError as err:
            # Handle general authorization failures
            msg = err.args[1] if len(err.args) > 1 else str(err)
            self.log(f"Authorization error on {phase}: {msg}", level="critical")
            raise

        except AuthorizationTimeoutError as err:
            # Handle token-refresh timeouts
            msg = err.args[1] if len(err.args) > 1 else str(err)
            self.log(f"Authorization timeout on {phase}: {msg}", level="error")
            raise

    def get_event_id(self, event: dict) -> str | None:
        """
        Extract the unique event ID from an event dict.
        Must be implemented by subclasses.

        Args:
            event: event dictionary

        Returns:
            unique event identifier, or None if not available
        """
        raise NotImplementedError("Subclasses must implement get_event_id()")

    @staticmethod
    def get_event_timestamp(event: dict) -> int | None:
        """
        Extract the event timestamp, in epoch milliseconds, from an event dict.

        Args:
            event: event dictionary

        Returns:
            timestamp in milliseconds, or None if not available/parseable
        """
        raw = event.get("timestamp")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def filter_processed_events(self, events: list[dict]) -> list[dict]:
        """
        Filter out events that have already been processed using the events cache.

        Args:
            events: list of event dictionaries

        Returns:
            filtered list containing only new events
        """
        filtered_events = []

        for event in events:
            event_id = self.get_event_id(event)

            # Corrupted or partial events without identifier are still forwarded,
            # but cannot be deduplicated.
            if event_id is None:
                filtered_events.append(event)
                continue

            # Check if the event id is already in the cache
            if event_id not in self.events_cache:
                # If not, add the event to the filtered list
                filtered_events.append(event)

                # Add the event id to the cache
                self.events_cache[event_id] = True

        return filtered_events

    def fetch_events(self) -> Generator[list[dict], None, None]:
        """
        Page through the API from the checkpoint, deduplicate, and yield new events.

        After each page is forwarded, persist a raw intermediate checkpoint so a crash
        replays at most one page (the replayed events are absorbed by the events cache).
        Once pagination is drained, persist the greatest timestamp seen + 1ms so the
        inclusive ``fromDate`` filter does not replay the last event on the next poll.
        """
        from_timestamp = self.most_recent_timestamp_seen
        most_recent_timestamp = from_timestamp

        for events in self._get_pages(
            endpoint=self.endpoint,
            params={
                "filters.fromDate": from_timestamp,
                "pagination.pageSize": self.configuration.chunk_size,
                "pagination.realtime": True,
            },
        ):
            # track the greatest timestamp seen in this page
            timestamps = [ts for ts in (self.get_event_timestamp(event) for event in events) if ts is not None]
            page_max = max(timestamps) if timestamps else None

            filtered_events = self.filter_processed_events(events)
            if filtered_events:
                yield filtered_events

            # resumed once the consumer has pushed the page: advance the checkpoint to
            # the raw page maximum so a restart replays at most this page
            if page_max is not None and page_max > most_recent_timestamp:
                most_recent_timestamp = page_max
                with self.context as cache:
                    cache["most_recent_timestamp_seen"] = most_recent_timestamp

        # pagination drained: +1ms to skip the last event on the inclusive fromDate filter
        if most_recent_timestamp > from_timestamp:
            with self.context as cache:
                cache["most_recent_timestamp_seen"] = most_recent_timestamp + 1

        now = datetime.now(UTC)
        current_lag = now - datetime.fromtimestamp(most_recent_timestamp / 1000, tz=UTC)
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        """
        Fetch new events, serialize and push them to intake, then sleep the remaining
        time until the next batch.
        """
        # Save the starting time
        batch_start_time = time.time()

        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # If the batch is not empty, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)

                self.save_events_cache()
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # Get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # Compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="debug",
            )
            time.sleep(delta_sleep)

    def run(self) -> None:
        """
        Continuously fetch and forward events until the connector is asked to stop.
        A failed batch is logged and retried on the next iteration.
        """
        self.log(message=f"Start fetching {self.NAME} events", level="info")

        try:
            while not self._stop_event.is_set():
                try:
                    self.next_batch()
                except Exception as error:
                    self.log_exception(error, message="Failed to fetch events")

        finally:
            # Cleanup on stop or fatal error
            if self._client is not None:
                # Use _client directly to close only an already-instantiated client,
                # avoiding lazy creation of a fresh client just to immediately close it.
                # Reset to None forces the property to create a new one on next run,
                # preventing "Cannot send a request, as the client has been closed." errors.
                self._client.close()
                self._client = None
            self.save_events_cache()
            self.log(message=f"Stopped fetching {self.NAME} events", level="info")
