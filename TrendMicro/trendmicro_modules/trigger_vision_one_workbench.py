import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Generator
from urllib.parse import urljoin

import orjson
import requests
from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import TrendMicroModule
from .client import TrendMicroVisionApiClient
from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class TrendMicroVisionOneWorkbenchConnectorConfiguration(DefaultConnectorConfiguration):
    base_url: str = Field(..., description="Base URL")
    api_key: str = Field(..., description="API key", secret=True)
    frequency: int = Field(60, description="Batch frequency in seconds", ge=1)


class TrendMicroVisionOneWorkbenchConnector(Connector):
    module: TrendMicroModule
    configuration: TrendMicroVisionOneWorkbenchConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path, start_at=timedelta(minutes=1), ignore_older_than=timedelta(hours=1)
        )
        self.from_date = self.cursor.offset

    @cached_property
    def client(self) -> TrendMicroVisionApiClient:
        return TrendMicroVisionApiClient(api_key=self.configuration.api_key)

    def __handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Trend Micro Vision One API to fetch events failed with status {response.status_code} - {response.reason}"
            level = "critical" if response.status_code in [401, 403] else "error"

            # enrich error logs with detail from the Okta API
            try:
                error = response.json()["error"]
                logger.error(
                    message, error_code=error["code"], error_message=error["message"], error_number=error["number"]
                )

            except Exception:
                pass

            self.log(message, level=level)

    def __fetch_events(self, from_date: datetime) -> Generator[list, None, None]:
        to_date = datetime.now(timezone.utc)

        query_params = {
            "startDateTime": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dateTimeTarget": "createdDateTime",
            "orderBy": "createdDateTime asc",
        }

        url = urljoin(self.configuration.base_url, "v3.0/workbench/alerts")
        response = self.client.get(url, params=query_params, timeout=60)

        while self.running:
            self.__handle_response_error(response)

            message = response.json()
            events = message.get("items", [])

            if events:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key, type="vision_one").inc(len(events))
                yield events

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="vision_one").set(0)
                return

            url = message.get("nextLink")
            if url is None:
                return

            response = self.client.get(url, timeout=60)

    @staticmethod
    def get_upper_second(time: datetime) -> datetime:
        """
        Return the upper second from a datetime

        :param datetime time: The starting datetime
        :return: The upper second of the starting datetime
        :rtype: datetime
        """
        return (time + timedelta(seconds=1)).replace(microsecond=0)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events in self.__fetch_events(most_recent_date_seen):
            if next_events:
                last_event = max(next_events, key=lambda x: x["createdDateTime"])
                last_event_datetime = isoparse(last_event["createdDateTime"])

                if last_event_datetime > most_recent_date_seen:
                    most_recent_date_seen = self.get_upper_second(last_event_datetime)

                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            self.cursor.offset = self.from_date

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type="vision_one").set(
            int(current_lag.total_seconds())
        )

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
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, type="vision_one").inc(
                    len(batch_of_events)
                )
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="debug")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key, type="vision_one").observe(
            batch_duration
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="debug")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching Trend Micro Vision One logs", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
