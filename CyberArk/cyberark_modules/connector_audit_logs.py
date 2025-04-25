import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
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


class CyberArkAuditLogsConnector(Connector):
    module: CyberArkModule
    configuration: CyberArkAuditLogsConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            time_unit=TimeUnit.MILLISECOND,
            path=self._data_path,
            start_at=timedelta(hours=1),
            ignore_older_than=timedelta(days=7),
        )

        self.from_date: int = self.cursor.offset
        self.events_cache: Cache = self.load_events_cache()

    def load_events_cache(self) -> Cache:
        result: LRUCache = LRUCache(maxsize=1000)

        with self.cursor._context as cache:
            events_ids = cache.get("events_cache", [])

        for event_id in events_ids:
            result[event_id] = 1

        return result

    def save_events_cache(self, events_cache: Cache) -> None:
        with self.cursor._context as cache:
            cache["events_cache"] = list(events_cache.keys())

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
        )

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"

            message = f"Request to CyberArk API failed with status {response.status_code} - {response.reason}"

            try:
                error = response.json()

                if code := error.get("code"):
                    message += f" error_code={code}"
                if message := error.get("message"):
                    message += f" error_message={message}"
                if description := error.get("description"):
                    message += f" error_description={description}"

            except Exception as e:
                pass

            self.log(message=message, level=level)
            response.raise_for_status()

    def __fetch_next_events(self, from_timestamp: int) -> Generator[list, None, None]:
        # 1. Create query
        from_date = datetime.fromtimestamp(from_timestamp / 1000.0).astimezone(timezone.utc)

        url = f"{self.configuration.api_base_url}/api/audits/stream/createQuery"

        try:
            response = self.client.post(
                url,
                json={
                    "query": {
                        "pageSize": 100,
                        "filterModel": {"date": {"dateFrom": from_date.isoformat()}},
                        "sortModel": [{"field_name": "date", "direction": "asc"}],
                    }
                },
            )
            self._handle_response_error(response)

        except AuthorizationFailedException as error:
            self.log_exception(error, level="critical")
            raise

        # Iterate through pages
        cursor_ref = response.json().get("cursorRef")
        if cursor_ref is None:
            logger.error(
                "Missing cursorRef from API response",
                from_timestamp=from_timestamp,
                response_content=response.text,
                response_status=response.status_code,
            )
            return

        while self.running:
            # 2. Get results by cursor ref
            url = f"{self.configuration.api_base_url}/api/audits/stream/results"
            response = self.client.post(url, json={"cursorRef": cursor_ref})
            self._handle_response_error(response)

            raw = response.json()

            items = raw["data"]
            cursor_ref = raw["paging"]["cursor"]["cursorRef"]

            if len(items) > 0:
                yield items

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                return

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if not next_events:
                continue

            filtered_events = [event for event in next_events if event["uuid"] not in self.events_cache]
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(filtered_events))

            if not filtered_events:
                continue

            # CyberArk API ignores datetime differences less than a second (even though the format includes
            # milliseconds). Thus, we have to make sure we don't get the same events multiple times.
            for event in next_events:
                event_uuid = event["uuid"]
                self.events_cache[event_uuid] = 1

            latest_event = max(filtered_events, key=lambda e: e["timestamp"])
            latest_event_timestamp = latest_event["timestamp"]

            yield filtered_events

            if latest_event_timestamp > most_recent_date_seen:
                most_recent_date_seen = latest_event_timestamp

        self.save_events_cache(self.events_cache)

        if most_recent_date_seen > self.from_date:
            self.cursor.offset = most_recent_date_seen
            self.from_date = most_recent_date_seen

            now = int(time.time())
            current_lag = now - most_recent_date_seen // 1000
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

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
