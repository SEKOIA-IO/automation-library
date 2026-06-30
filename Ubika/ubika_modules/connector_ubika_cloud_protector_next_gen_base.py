import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from functools import cached_property
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
from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from .timestepper import TimeStepper


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
    timedelta: int = Field(
        5,
        description="The temporal shift, in the past, in minutes, the connector applies when fetching the events",
        ge=1,
    )
    start_time: int = Field(1, description="The number of hours from which events should be queried", ge=0)


class UbikaCloudProtectorNextGenBaseConnector(Connector):
    """
    Base class for Next-Gen connectors. Provides:

      • `self.client` (@cached_property) for HTTP+auth
      • `_handle_response_error()`
      • `_get_pages(endpoint, params)` for cursor+token pagination
      • `self.context` (PersistentJSON) to store a checkpoint
      • common config in UbikaCloudProtectorNextGenBaseConnectorConfiguration
      • Generic `next_batch()` and `filter_processed_events()` for subclasses
    """

    module: UbikaModule

    NAME: str = "Ubika Cloud Protector NextGen Base"
    configuration: UbikaCloudProtectorNextGenBaseConnectorConfiguration

    cache_size: int = 1000  # Default cache size, can be overridden in subclasses
    endpoint: str = ""  # Must be set by subclasses (e.g., "security-events", "traffic-logs")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Single file to store our checkpoint
        self.context = PersistentJSON("context.json", self.data_path)
        # Cache context for storing event hashes
        self.cache_context = PersistentJSON("cache.json", self.data_path)
        self.events_cache: Cache = self.load_events_cache()
        # HTTP client for API requests (lazily initialized)
        self._client: UbikaCloudProtectorNextGenApiClient | None = None

    @cached_property
    def scalability_labels(self) -> dict[str, str]:
        """Get scalability labels from module manifest."""
        labels = self.module.manifest.get("labels", {})
        scalable_horizontally = str(labels.get("scalable_horizontally", False)).lower()
        scalable_vertically = str(labels.get("scalable_vertically", False)).lower()
        return {
            "scalable_horizontally": scalable_horizontally,
            "scalable_vertically": scalable_vertically,
        }

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

    @cached_property
    def stepper(self) -> TimeStepper:
        """
        Create a TimeStepper instance to manage time ranges for event collection.
        Reads the most recent date from context, or creates a new one if not found.
        """
        with self.context as cache:
            most_recent_date_str = cache.get("most_recent_date_seen")

            # If not defined, create a new time stepper from the configuration
            if most_recent_date_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            # Parse the most recent requested date
            most_recent_date = isoparse(most_recent_date_str)

            # Ensure we do not go back more than one month
            now = datetime.now(UTC)
            one_month_ago = now - timedelta(days=30)
            # If the most recent date is older than one month, set it to one month ago
            if most_recent_date < one_month_ago:
                most_recent_date = one_month_ago

            # Create a time stepper from the most recent date seen
            return TimeStepper.create_from_time(
                self,
                most_recent_date,
                self.configuration.frequency,
                self.configuration.timedelta,
            )

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
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key, **self.scalability_labels).inc(
                len(items)
            )
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

    def next_batch(self, start: datetime, end: datetime) -> None:
        """
        Fetch pages for the given time range, serialize and push events to intake.
        Updates the checkpoint with the end time.

        Args:
            start: start time of the batch window
            end: end time of the batch window
        """
        # Save the starting time
        batch_start_time = time.time()
        start_timestamp = int(start.timestamp() * 1000)
        end_timestamp = int(end.timestamp() * 1000)

        # Fetch all pages for this time range
        for events in self._get_pages(
            endpoint=self.endpoint,
            params={
                "filters.fromDate": start_timestamp,
                "filters.toDate": end_timestamp,
                "pagination.pageSize": self.configuration.chunk_size,
                "pagination.realtime": True,
            },
        ):
            filtered_events = self.filter_processed_events(events)
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in filtered_events]

            # If the batch is not empty, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, **self.scalability_labels).inc(
                    len(batch_of_events)
                )
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # Just in case
        self.save_events_cache()

        # Update checkpoint with the end time of this batch
        with self.context as cache:
            cache["most_recent_date_seen"] = end.isoformat()

        # Get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, **self.scalability_labels).observe(
            batch_duration
        )

    def run(self) -> None:
        """
        Main loop using TimeStepper to manage time ranges:
        1) Use stepper.ranges() to get successive time windows
        2) For each window, call next_batch() to fetch and push events
        3) Stepper manages sleep timing and lag handling
        """
        self.log(message=f"Start fetching {self.NAME} events", level="info")

        try:
            for start, end in self.stepper.ranges():
                # Check if we need to stop
                if self._stop_event.is_set():
                    break

                try:
                    self.next_batch(start, end)
                except Exception as error:
                    self.log_exception(error, message="Failed to fetch events")
                    break

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
