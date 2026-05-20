from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

import httpx
from dateutil.parser import isoparse
from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import UbikaModule
from .client import UbikaCloudProtectorNextGenApiClient
from .client.auth import AuthorizationError, AuthorizationTimeoutError
from .metrics import INCOMING_MESSAGES
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
    """

    module: UbikaModule

    NAME: str = "Ubika Cloud Protector NextGen Base"
    configuration: UbikaCloudProtectorNextGenBaseConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Single file to store our checkpoint
        self.context = PersistentJSON("context.json", self.data_path)

    @cached_property
    def client(self) -> UbikaCloudProtectorNextGenApiClient:
        """
        HTTP client that automatically injects tokens and handles rate‐limits.
        """
        return UbikaCloudProtectorNextGenApiClient(refresh_token=self.configuration.refresh_token)

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
