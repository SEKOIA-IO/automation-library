import time
from collections.abc import Generator
from datetime import datetime, timezone

import httpx
import orjson
from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from .client import UbikaCloudProtectorNextGenApiClient
from .client.auth import AuthorizationError, AuthorizationTimeoutError


class FetchEventsException(Exception):
    pass


class UbikaCloudProtectorNextGenTrafficLogsConnectorConfiguration(DefaultConnectorConfiguration):
    """
    Configuration for the Ubika traffic-logs connector.
    """

    namespace: str = Field(..., description="Namespace")
    refresh_token: str = Field(..., description="API refresh token", secret=True)

    frequency: int = Field(60, description="Batch frequency in seconds")
    chunk_size: int = Field(200, description="The size of chunks for the batch processing")
    # Back-fill window on first run, in hours
    start_time: int = Field(1, description="The number of hours from which events should be queried", ge=0)


class UbikaCloudProtectorNextGenTrafficLogsConnector(Connector):
    """
    Connector that continuously polls the Ubika Cloud Protector NextGen
    traffic-logs endpoint and forwards them to the configured intake.
    """

    NAME = "Ubika Cloud Protector NextGen Traffic Logs"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Where we persist the last‐seen timestamp
        self.context = PersistentJSON("context.json", self.data_path)
        # HTTP client that handles authentication and token refresh
        self.client = UbikaCloudProtectorNextGenApiClient(refresh_token=self.configuration.refresh_token)

    def _handle_response_error(self, response: httpx.Response) -> None:
        """
        Raise if the HTTP response status is not 2xx.
        """
        if not response.is_success:
            try:
                err = response.json()
            except ValueError:
                err = response.text
            msg = f"[{self.NAME}] HTTP {response.status_code} error: " f"{err} for {response.request.url}"
            raise FetchEventsException(msg)

    def _fetch_pages(self, start_timestamp: int) -> Generator[list[dict], None, None]:
        """
        Yield pages of traffic logs from `filters.fromDate = start_timestamp`
        until no more pages are returned.
        A page is a batch of results returned in a single paginated API response.
        """
        # Build URL using the configured namespace
        url = f"https://api.ubika.io/rest/logs.ubika.io/v1" f"/ns/{self.configuration.namespace}/traffic-logs"
        headers = {"Content-Type": "application/json"}

        # Initial parameters include fromDate and pageSize
        params = {
            "filters.fromDate": start_timestamp,
            "pagination.pageSize": self.configuration.chunk_size,
        }

        # First request using UbikaCloudProtectorNextGenApiClient
        try:
            response = self.client.get(url, params=params, headers=headers, timeout=60)
        except AuthorizationError as e:
            self.log(f"Authorization error on initial fetch: {e}", level="critical")
            raise
        except Exception as e:
            self.log(f"Request failure on initial fetch: {e}", level="error")
            raise

        # Loop as long as the connector is running
        while self.running:
            # Centralized HTTP error handling
            self._handle_response_error(response)

            # Parse the HTTP response body into a Python dict
            payload = response.json()

            # Extract events from the 'spec.items' field
            items = payload.get("spec", {}).get("items", [])
            if not items:
                # Stop when the list of events is empty
                return

            # Yield the current batch of items
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
            try:
                response = self.client.get(
                    url,
                    params={
                        "pagination.pageToken": token,
                        "pagination.pageSize": self.configuration.chunk_size,
                    },
                    headers=headers,
                    timeout=60,
                )
            except AuthorizationTimeoutError as err:
                # Handle token-refresh timeouts
                self.log(f"Authorization timeout error: {err.args[1]}", level="error")
                raise
            except AuthorizationError as err:
                # Handle general authorization failures
                self.log(f"Authorization error: {err.args[1] if len(err.args) > 1 else str(err)}", level="critical")
                raise


def run(self) -> None:
    """
    Main loop:
      1) Load last checkpoint (milliseconds since epoch)
      2) Fetch pages of new logs via _fetch_pages()
      3) For each page:
           - publish to intake
           - track highest timestamp seen
      4) Save new checkpoint
      5) Sleep for `frequency` seconds and repeat
    """
    self.log(f"Start fetching {self.NAME} events", level="info")

    # Initialize or load checkpoint
    with self.context as cache:
        # Read the last checkpoint (ms since epoch)
        # from the <self.data_path>/context.json file (PersistentJSON)
        last_ts = cache.get("most_recent_timestamp_seen")
    if not last_ts or last_ts <= 0:
        # If no valid checkpoint is found, back-fill X hours on first run
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        backfill_ms = self.configuration.start_time * 3600 * 1000
        last_ts = now_ms - backfill_ms
    self.log(f"Initial start timestamp: {last_ts}", level="debug")

    # Polling loop
    while not self._stop_event.is_set():
        start_time = time.time()
        max_ts = last_ts

        try:
            for page in self._fetch_pages(last_ts):
                # Serialize and publish each page
                payloads = [orjson.dumps(evt).decode("utf-8") for evt in page]
                if payloads:
                    self.log(f"Publishing {len(payloads)} traffic-log events", level="info")
                    self.publish_events_to_intake(events=payloads)

                # Update the highest timestamp seen
                # This way we never re-consume older logs (we always move "forward" in time)
                # and we survive restarts because the last-seen timestamp is persisted on disk
                for evt in page:
                    try:
                        ts = int(evt.get("timestamp", 0))
                    except (TypeError, ValueError):
                        ts = 0
                    if ts > max_ts:
                        max_ts = ts

            # Persist new checkpoint after exhausting all pages of new logs
            with self.context as cache:
                cache["most_recent_timestamp_seen"] = max_ts
            last_ts = max_ts

        except Exception as e:
            self.log_exception(e, message="Error fetching traffic logs")

        finally:
            # Sleep before next poll
            elapsed = time.time() - start_time
            self.log(f"Iteration took {elapsed:.2f}s, sleeping {self.configuration.frequency}s", level="debug")
            time.sleep(self.configuration.frequency)

    # Cleanup on stop
    if hasattr(self, "client"):
        self.client.close()
    with self.context as cache:
        cache["most_recent_timestamp_seen"] = last_ts
    self.log(f"Stopped fetching {self.NAME} events", level="info")
