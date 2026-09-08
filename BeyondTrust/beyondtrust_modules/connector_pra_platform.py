from datetime import datetime, timedelta, timezone
from typing import Generator

from cachetools import Cache, LRUCache
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import DefaultConnectorConfiguration

from . import BeyondTrustModule
from .connector_base import BeyondTrustBaseConnector
from .helpers import parse_session, parse_session_end_time, parse_session_list
from .metrics import EVENTS_LAG, INCOMING_MESSAGES


class BeyondTrustPRAPlatformConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(5 * 60, description="Batch frequency in seconds")


class BeyondTrustPRAPlatformConnector(BeyondTrustBaseConnector):
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
        most_recent_date_seen = self.from_date

        response = self.client.get_session_listing(most_recent_date_seen)
        if self._handle_response_error(response):
            return

        if self._check_xml_error(response):
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
            return

        sessions_ids = parse_session_list(response.content)
        for session_id in sessions_ids:
            if session_id in self.sessions_cache:
                continue

            response = self.client.get_session(session_id)
            if self._handle_response_error(response):
                return

            session_end_time = parse_session_end_time(response.content)
            if session_end_time > most_recent_date_seen:
                most_recent_date_seen = session_end_time

            parsed_events = parse_session(response.content)
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(parsed_events))

            self.sessions_cache[session_id] = 1
            yield parsed_events

        self.save_sessions_cache(self.sessions_cache)

        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            self.cursor.offset = most_recent_date_seen

            now = int(datetime.now(timezone.utc).timestamp())
            current_lag = now - most_recent_date_seen
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)
