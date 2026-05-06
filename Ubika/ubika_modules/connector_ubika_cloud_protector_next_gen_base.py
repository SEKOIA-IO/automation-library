from collections.abc import Generator
from functools import cached_property
from typing import Any

import httpx
from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import UbikaModule
from .client import UbikaCloudProtectorNextGenApiClient
from .client.auth import AuthorizationError, AuthorizationTimeoutError
from .metrics import INCOMING_MESSAGES


class FetchEventsException(Exception):
    """Raised on non-2xx responses from the Ubika API."""


class UbikaCloudProtectorNextGenBaseConnectorConfiguration(DefaultConnectorConfiguration):
    """
    Common configuration for all NextGen connectors.
    """

    namespace: str = Field(..., description="Ubika namespace")
    refresh_token: str = Field(..., description="API refresh token", secret=True)

    frequency: int = Field(60, description="Polling interval in seconds", ge=1)
    chunk_size: int = Field(200, description="Page size for API calls", ge=1)


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
        # single file to store our checkpoint
        self.context = PersistentJSON("context.json", self.data_path)

    @cached_property
    def client(self) -> UbikaCloudProtectorNextGenApiClient:
        """
        HTTP client that automatically injects tokens and handles rate‐limits.
        """
        return UbikaCloudProtectorNextGenApiClient(refresh_token=self.configuration.refresh_token)

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
        base_url = f"https://api.ubika.io/rest/logs.ubika.io/v1" f"/ns/{self.configuration.namespace}/{endpoint}"
        headers = {"Content-Type": "application/json"}

        # First request using UbikaCloudProtectorNextGenApiClient
        response = self._safe_get(url=base_url, params=params, headers=headers, initial=True)

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
            response = self._safe_get(
                url=base_url,
                params={
                    "pagination.pageToken": token,
                    "pagination.pageSize": self.configuration.chunk_size,
                    "pagination.realtime": "true",
                },
                headers=headers,
                initial=False,
            )

    def _safe_get(self, url: str, *, params, headers, initial: bool) -> httpx.Response:
        """
        Wrap client.get and centralize the AuthorizationError / Timeout logging.
        initial=True means “on initial fetch”, otherwise “on next page”.
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
