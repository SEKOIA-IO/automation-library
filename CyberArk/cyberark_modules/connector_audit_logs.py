import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointCursor, CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import CyberArkModule
from .client import ApiClient
from .client.auth import AuthorizationFailedException, CyberArkApiAuthentication
from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class CyberArkAuditLogsConnectorConfiguration(DefaultConnectorConfiguration):
    api_base_url: str = Field(..., description="API base url")
    api_key: str = Field(..., description="API key", secret=True)
    frequency: int = Field(60, description="Batch frequency in seconds")


class CursorExpiredError(Exception):
    """The SIEM integration API rejected the cursor (403)"""


class CyberArkAuditLogsConnector(Connector):
    module: CyberArkModule
    configuration: CyberArkAuditLogsConnectorConfiguration

    # The SIEM integration API can only be called once a minute
    API_RATELIMIT_PER_MINUTE = 1
    # Maximum page size allowed by the SIEM integration API
    PAGE_SIZE = 500
    # Delay before retrying a batch after an error
    ERROR_BACKOFF_SECONDS = 60

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # The stream cursor is used to resume the events retrieval from one batch to another.
        # The timestamp is used to create a new query when there is no cursor or when it was rejected.
        self.timestamp_checkpoint = CheckpointTimestamp(
            time_unit=TimeUnit.MILLISECOND,
            path=self._data_path,
            start_at=timedelta(hours=1),
            ignore_older_than=timedelta(days=7),
        )
        self.cursor_checkpoint = CheckpointCursor(path=self._data_path)

        # Both checkpoints must share the same context: each PersistentJSON instance keeps its own copy
        # of context.json in memory and would overwrite the fields saved by the other one
        self.context = self.timestamp_checkpoint._context
        self.cursor_checkpoint._context = self.context

        self.from_date: int = self.timestamp_checkpoint.offset
        self.events_cache: Cache = self.load_events_cache()

    def load_events_cache(self) -> Cache:
        result: LRUCache = LRUCache(maxsize=1000)

        with self.context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = 1

        return result

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            auth=CyberArkApiAuthentication(
                auth_base_url=self.module.configuration.auth_base_url,
                application_id=self.module.configuration.application_id,
                client_id=self.module.configuration.login_name,
                client_secret=self.module.configuration.password,
                api_key=self.configuration.api_key,
            ),
            ratelimit_per_minute=self.API_RATELIMIT_PER_MINUTE,
        )

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"

            message = f"Request to CyberArk API failed with status {response.status_code} - {response.reason}"

            try:
                error = response.json()

                if code := error.get("code"):
                    message += f" error_code={code}"
                if error_message := error.get("message"):
                    message += f" error_message={error_message}"
                if description := error.get("description"):
                    message += f" error_description={description}"

            except Exception as e:
                pass

            self.log(message=message, level=level)
            response.raise_for_status()

    def _create_query(self, from_timestamp: int) -> str | None:
        """
        Create a query starting at `from_timestamp` and return its stream cursor
        """
        from_date = datetime.fromtimestamp(from_timestamp / 1000.0).astimezone(timezone.utc)

        url = f"{self.configuration.api_base_url}/api/audits/stream/createQuery"

        try:
            response = self.client.post(
                url,
                json={
                    "query": {
                        "pageSize": self.PAGE_SIZE,
                        "filterModel": {"date": {"dateFrom": from_date.isoformat()}},
                        "sortModel": [{"field_name": "date", "direction": "asc"}],
                    }
                },
            )
            self._handle_response_error(response)

        except AuthorizationFailedException as error:
            self.log_exception(error, level="critical")
            raise

        cursor_ref = response.json().get("cursorRef")
        if cursor_ref is None:
            logger.error(
                "Missing cursorRef from API response",
                from_timestamp=from_timestamp,
                response_content=response.text,
                response_status=response.status_code,
            )

        return cursor_ref

    def _fetch_page(self, cursor_ref: str) -> dict:
        """
        Fetch the next page of the stream
        """
        url = f"{self.configuration.api_base_url}/api/audits/stream/results"
        response = self.client.post(url, json={"cursorRef": cursor_ref})

        # The API answers with a 403 when the cursor is no longer valid
        if response.status_code == 403:
            raise CursorExpiredError(f"Cursor rejected by CyberArk API with status 403 - {response.reason}")

        self._handle_response_error(response)
        return response.json()

    def __fetch_next_events(self) -> Generator[tuple[list, str], None, None]:
        """
        Iterate over the pages of the stream and yield their events along with the cursor of the next page
        """
        stored_cursor_ref: str | None = self.cursor_checkpoint.offset
        # A stored cursor can be recreated once if rejected, a fresh one can't
        can_recreate_cursor = stored_cursor_ref is not None

        if stored_cursor_ref is None:
            stored_cursor_ref = self._create_query(self.from_date)
            if stored_cursor_ref is None:
                return

        cursor_ref: str = stored_cursor_ref

        while self.running:
            try:
                raw = self._fetch_page(cursor_ref)

            except CursorExpiredError as error:
                if not can_recreate_cursor:
                    self.log(message=f"{error} on a new cursor", level="critical")
                    raise

                self.log(message=f"{error}, creating a new query", level="warning")
                can_recreate_cursor = False
                self.cursor_checkpoint.offset = None
                new_cursor_ref = self._create_query(self.from_date)
                if new_cursor_ref is None:
                    return

                cursor_ref = new_cursor_ref
                continue

            items = raw["data"]
            cursor_ref = raw["paging"]["cursor"]["cursorRef"]

            yield items, cursor_ref

            # The stream is up to date: keep the cursor for the next batch
            if len(items) == 0:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                return

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events, next_cursor_ref in self.__fetch_next_events():
            filtered_events = [event for event in next_events if event["uuid"] not in self.events_cache]
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(filtered_events))

            if filtered_events:
                yield filtered_events

                # Only mark the events as seen once they have been forwarded: if the push fails,
                # the page will be fetched again and its events must not be filtered out.
                # CyberArk API ignores datetime differences less than a second (even though the format includes
                # milliseconds). Thus, we have to make sure we don't get the same events multiple times.
                for event in next_events:
                    event_uuid = event["uuid"]
                    self.events_cache[event_uuid] = 1

                latest_event = max(filtered_events, key=lambda e: e["timestamp"])
                most_recent_date_seen = max(most_recent_date_seen, latest_event["timestamp"])

            # Save the checkpoint after each page, once its events have been forwarded,
            # so that an error on a later page doesn't make us fetch them again
            self.save_checkpoint(most_recent_date_seen, next_cursor_ref)

    def save_checkpoint(self, most_recent_date_seen: int, cursor_ref: str) -> None:
        # Save the events cache, the timestamp and the cursor at once so that they are always consistent
        with self.context as cache:
            cache["events_cache"] = list(self.events_cache.keys())

            if most_recent_date_seen > self.from_date:
                cache["most_recent_date_seen"] = self.timestamp_checkpoint.datetime_to_file(
                    self.timestamp_checkpoint.to_datetime(most_recent_date_seen)
                )
                self.from_date = most_recent_date_seen

                now = int(time.time())
                current_lag = now - most_recent_date_seen // 1000
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

            cache["cursor"] = cursor_ref

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(message=f"Fetched and forwarded events in {batch_duration} seconds", level="debug")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="debug")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching CyberArk audit logs", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
                # Wait before retrying so we don't hammer the API (e.g. after a 429 Too Many Requests)
                time.sleep(self.ERROR_BACKOFF_SECONDS)
