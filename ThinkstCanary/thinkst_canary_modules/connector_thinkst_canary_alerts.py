import time
from datetime import datetime, timezone
from functools import cached_property
from typing import Generator
from urllib.parse import urljoin

import dateutil
import orjson
import requests
import structlog
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import ThinkstCanaryModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class ThinksCanaryAlertsConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 10


logger = structlog.getLogger()


class ThinkstCanaryAlertsConnector(Connector):
    module: ThinkstCanaryModule
    configuration: ThinksCanaryAlertsConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.from_id = self.most_recent_id_seen

    @cached_property
    def client(self):
        return ApiClient(base_url=self.module.configuration.base_url, auth_token=self.module.configuration.auth_token)

    @property
    def most_recent_id_seen(self) -> int:
        with self.context as cache:
            most_recent_id_seen = cache.get("most_recent_id_seen")

        if isinstance(most_recent_id_seen, str):
            most_recent_id_seen = int(most_recent_id_seen)

        return most_recent_id_seen

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            logger.error(
                "failed to fetch events",
                status_code=response.status_code,
                content=response.text,
            )
            self.log(level="error", message="failed to fetch events")

    def fetch_pages(self, from_id: int | None) -> Generator[dict, None, None]:
        # Iterate through pages
        url = urljoin(self.client.base_url, "/api/v1/incidents/unacknowledged")
        params = (
            {"limit": self.configuration.chunk_size, "incidents_since": from_id}
            if from_id
            else {"limit": self.configuration.chunk_size}
        )
        response = self.client.get(url=url, params=params)

        while self.running:
            self._handle_response_error(response)

            page = response.json()

            if len(page["incidents"]) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(page["incidents"]))
                yield page

            else:
                return

            cursor = page.get("cursor", {}).get("next")
            if not cursor:
                return

            response = self.client.get(url, params={"cursor": cursor})

    @staticmethod
    def extract_events(page: dict) -> list[dict]:
        incidents = page["incidents"]

        records = []
        for incident in incidents:
            # get the description of the incident and remove it from the incident
            description = incident.pop("description", {})

            # extract the incident id
            incident_id = incident["id"]

            # add the incident (without its description) as a record
            records.append(
                {
                    "incident_id": incident["id"],
                    "event_type": "incident",
                    "summary": incident["summary"],
                    "timestamp": incident["updated_time"],
                }
            )

            # get the events from the incident
            events = description.pop("events", [])

            # remove events_count and events_list from the description
            description.pop("events_count")
            description.pop("events_list")

            for event in events:
                record = {"incident_id": incident_id, "event_type": "event"}
                record.update(description)
                record.update(event)
                records.append(record)

        return records

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_id_seen = self.from_id
        most_recent_timestamp_seen = None  # for the event lag calculation

        try:
            for next_page in self.fetch_pages(most_recent_id_seen):
                events = self.extract_events(next_page)
                last_event_id = next_page["max_updated_id"]
                if most_recent_id_seen is None or last_event_id > most_recent_id_seen:
                    most_recent_id_seen = last_event_id

                if len(events) > 0:
                    most_recent_timestamp_seen = dateutil.parser.parse(next_page["updated_std"])
                    yield events

        finally:
            if self.from_id is None or most_recent_id_seen > self.from_id:
                self.from_id = most_recent_id_seen

                with self.context as cache:
                    cache["most_recent_id_seen"] = most_recent_id_seen

        if most_recent_timestamp_seen:
            # no events - no lag
            now = datetime.now(timezone.utc)
            current_lag = now - most_recent_timestamp_seen
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

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
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching Thinkst Canary alerts", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
