import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Generator

import orjson
import requests
from pydantic.v1 import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from .client import TrendMicroVisionApiClient
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


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

    def handle_response_error(self, response: requests.Response) -> None:  # pragma: no cover
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"
            error_code = None
            error_message = None
            error_number = None
            try:
                response_data = response.json()
                if isinstance(response_data, dict):
                    error = response_data.get("error")
                    if isinstance(error, dict):
                        error_code = error.get("code")
                        error_message = error.get("message")
                        error_number = error.get("number")

            except ValueError:
                pass

            self.log(
                (
                    "Vision One API request failed "
                    f"status_code={response.status_code} "
                    f"reason={response.reason} "
                    f"error_code={error_code} "
                    f'error_message="{error_message}" '
                    f"error_number={error_number}"
                ),
                level=level,
            )

    @staticmethod
    def get_upper_second(time: datetime) -> datetime:
        """
        Return the upper second from a datetime

        :param datetime time: The starting datetime
        :return: The upper second of the starting datetime
        :rtype: datetime
        """
        return (time + timedelta(seconds=1)).replace(microsecond=0)

    def sanitize_from_date(self, from_date: datetime) -> datetime:
        """
        Ensure the cursor date is not in the future to avoid empty polling windows.

        :param datetime from_date: Cursor date to validate
        :return: A safe cursor date
        :rtype: datetime
        """
        now = datetime.now(timezone.utc)
        if from_date > now:
            self.log(
                (
                    "Future checkpoint detected "
                    f"previous_checkpoint={from_date.isoformat()} "
                    f"new_checkpoint={now.isoformat()}"
                ),
                level="warning",
            )
            return now

        return from_date

    @abstractmethod
    def fetch_events(self) -> Generator[list, None, None]:
        raise NotImplementedError

    def reset_cursor_offset(self, offset: datetime) -> None:
        """
        Persist a checkpoint value even if it moves backward in time.

        CheckpointDatetime only moves forward through its public setter.
        We use this path when recovering from an invalid future checkpoint.
        """
        self.cursor._most_recent_date_seen = offset
        lock = getattr(self.cursor, "_lock", None)
        if lock:
            lock.acquire()

        try:
            with self.cursor._context as cache:
                subkey = getattr(self.cursor, "_subkey", None)
                serialized_offset = self.cursor.datetime_to_file(offset)
                if subkey:
                    if subkey not in cache:
                        cache[subkey] = {}
                    cache[subkey]["most_recent_date_seen"] = serialized_offset
                else:
                    cache["most_recent_date_seen"] = serialized_offset
        finally:
            if lock:
                lock.release()

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()
        total_events_forwarded = 0

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]
            events_count = len(batch_of_events)

            # if the batch is full, push it
            if events_count > 0:
                self.log(
                    message=(
                        "Forwarded events batch "
                        f"connector={self.CONNECTOR_METRICS_LABEL} "
                        f"events_forwarded={events_count}"
                    ),
                    level="info",
                )
                OUTCOMING_EVENTS.labels(
                    intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
                ).inc(events_count)
                self.push_events_to_intakes(events=batch_of_events)
                total_events_forwarded += events_count
            else:
                self.log(
                    message=(
                        "No events to forward " f"connector={self.CONNECTOR_METRICS_LABEL} " "events_forwarded=0"
                    ),
                    level="debug",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            (
                "Batch processing completed "
                f"connector={self.CONNECTOR_METRICS_LABEL} "
                f"events_forwarded_total={total_events_forwarded} "
                f"duration_seconds={batch_duration}"
            ),
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(
            intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
        ).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                (
                    "Sleeping before next batch "
                    f"connector={self.CONNECTOR_METRICS_LABEL} "
                    f"wait_seconds={delta_sleep}"
                ),
                level="debug",
            )
            time.sleep(delta_sleep)

    def run(self) -> None:  # pragma: no cover
        self.log(
            message=(
                "Starting connector polling "
                f'connector_title="{self.CONNECTOR_TITLE}" '
                f"connector={self.CONNECTOR_METRICS_LABEL} "
                f"frequency_seconds={self.configuration.frequency}"
            ),
            level="info",
        )

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(
                    error,
                    message=("Batch processing failed " f"connector={self.CONNECTOR_METRICS_LABEL}"),
                )
