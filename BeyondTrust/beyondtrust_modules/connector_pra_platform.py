import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import BeyondTrustModule
from .client import ApiClient
from .helpers import parse_session, parse_session_end_time, parse_session_list
from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class BeyondTrustPRAPlatformConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(5 * 60, description="Batch frequency in seconds")


class BeyondTrustPRAPlatformConnector(Connector):
    module: BeyondTrustModule
    configuration: BeyondTrustPRAPlatformConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            time_unit=TimeUnit.SECOND,
            path=self._data_path,
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=7),
        )
        self.from_date = self.cursor.offset
        self.sessions_cache: Cache = self.load_sessions_cache()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"

            message = f"Request to BeyondTrust API failed with status {response.status_code} - {response.reason}"

            # enrich error logs with detail from the Okta API
            try:
                error = response.json()
                logger.error(
                    message,
                    error_message=error.get("message"),
                    error_number=error.get("number"),
                )

            except Exception as e:
                pass

            self.log(message=message, level=level)

    def load_sessions_cache(self) -> Cache:
        result: LRUCache = LRUCache(maxsize=1000)

        with self.cursor._context as cache:
            sessions_ids = cache.get("sessions_cache", [])

        for session_id in sessions_ids:
            result[session_id] = 1

        return result

    def save_sessions_cache(self, sessions: Cache) -> None:
        with self.cursor._context as cache:
            cache["sessions_cache"] = list(sessions.keys())

    def fetch_events(self) -> Generator[list, None, None]:
        # 1. Get list of sessions
        # 2. Download details for every session
        most_recent_date_seen = self.from_date

        response = self.client.post(
            f"{self.module.configuration.base_url}/api/reporting",
            data={"generate_report": "AccessSessionListing", "duration": 0, "end_time": most_recent_date_seen},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )
        self._handle_response_error(response)

        if "<error>" in response.text and response.status_code == 200:
            # no sessions
            self.log(response.text, level="debug")
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            return

        sessions_ids = parse_session_list(response.content)
        for session_id in sessions_ids:
            if session_id in self.sessions_cache:
                continue

            # request and parse each session - doing this iteratively, because we have 20 requests per second limit
            response = self.client.post(
                f"{self.module.configuration.base_url}/api/reporting",
                data={"generate_report": "AccessSession", "lsid": session_id},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60,
            )
            self._handle_response_error(response)

            session_end_time = parse_session_end_time(response.content)
            if session_end_time > most_recent_date_seen:
                most_recent_date_seen = session_end_time

            parsed_events = parse_session(response.content)
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(parsed_events))

            self.sessions_cache[session_id] = 1
            yield parsed_events

        # save sessions cache to the context
        self.save_sessions_cache(self.sessions_cache)

        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            self.cursor.offset = most_recent_date_seen

            now = int(datetime.now(timezone.utc).timestamp())
            current_lag = now - most_recent_date_seen
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def next_batch(self):
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
        self.log(message=f"Fetched and forwarded events in {batch_duration} seconds", level="info")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching BeyondTrust events", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
