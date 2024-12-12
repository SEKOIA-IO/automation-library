import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from functools import cached_property
from typing import Generator

import orjson
import requests
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from .client import TrendMicroVisionApiClient
from .logging import get_logger
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

logger = get_logger()


class TrendMicroVisionOneBaseConfiguration(DefaultConnectorConfiguration):
    base_url: str = Field(..., description="Base URL")
    api_key: str = Field(..., description="API key", secret=True)
    frequency: int = Field(60, description="Batch frequency in seconds", ge=1)


class TrendMicroVisionOneBaseConnector(Connector, ABC):
    configuration: TrendMicroVisionOneBaseConfiguration

    CONNECTOR_METRICS_LABEL: str
    CONNECTOR_TITLE: str

    @cached_property
    def client(self) -> TrendMicroVisionApiClient:
        return TrendMicroVisionApiClient(api_key=self.configuration.api_key)

    def handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = (
                f"Request on Trend Micro Vision One API to fetch events failed with status "
                f"{response.status_code} - {response.reason}"
            )
            level = "critical" if response.status_code in [401, 403] else "error"

            # enrich error logs with detail from the Okta API
            try:
                error = response.json()["error"]
                logger.error(
                    message,
                    error_code=error.get("code"),
                    error_message=error.get("message"),
                    error_number=error.get("number"),
                )

            except Exception as e:
                pass

            self.log(message, level=level)

    @staticmethod
    def get_upper_second(time: datetime) -> datetime:
        """
        Return the upper second from a datetime

        :param datetime time: The starting datetime
        :return: The upper second of the starting datetime
        :rtype: datetime
        """
        return (time + timedelta(seconds=1)).replace(microsecond=0)

    @abstractmethod
    def fetch_events(self) -> Generator[list, None, None]:
        pass

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
                OUTCOMING_EVENTS.labels(
                    intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
                ).inc(len(batch_of_events))
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
        FORWARD_EVENTS_DURATION.labels(
            intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
        ).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="debug")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message=f"Start fetching {self.CONNECTOR_TITLE} alerts", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
