from datetime import datetime, timedelta, timezone
from typing import Generator
from urllib.parse import urljoin

from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointDatetime

from . import TrendMicroModule
from .logging import get_logger
from .metrics import EVENTS_LAG, INCOMING_MESSAGES
from .trigger_vision_one_base import TrendMicroVisionOneBaseConfiguration, TrendMicroVisionOneBaseConnector

logger = get_logger()


class TrendMicroVisionOneOATConnectorConfiguration(TrendMicroVisionOneBaseConfiguration):
    filter: str | None = Field(None, description="Filter for events", max_length=4000)


class TrendMicroVisionOneOATConnector(TrendMicroVisionOneBaseConnector):
    CONNECTOR_TITLE = "Trend Micro Vision One OAT"
    CONNECTOR_METRICS_LABEL = "vision_one_oat"

    module: TrendMicroModule
    configuration: TrendMicroVisionOneOATConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path, start_at=timedelta(hours=1), ignore_older_than=timedelta(days=14)
        )
        self.from_date = self.cursor.offset

    def __fetch_events(self, from_date: datetime) -> Generator[list, None, None]:
        to_date = datetime.now(timezone.utc)

        query_params: dict[str, str | int] = {
            "detectedStartDateTime": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "detectedEndDateTime": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "top": 200,  # items per page - could be 50, 100, 200
        }
        if self.configuration.filter is not None:
            headers = {"TMV1-Filter": self.configuration.filter}

        else:
            headers = {}

        url = urljoin(self.configuration.base_url, "v3.0/oat/detections")
        response = self.client.get(url, params=query_params, headers=headers, timeout=60)

        while self.running:
            self.handle_response_error(response)

            message = response.json()
            events = message.get("items", [])

            if events:
                INCOMING_MESSAGES.labels(
                    intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
                ).inc(len(events))
                yield events

            else:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL).set(0)
                return

            url = message.get("nextLink")
            if url is None:
                return

            response = self.client.get(url, timeout=60)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events in self.__fetch_events(most_recent_date_seen):
            if next_events:
                last_event = max(next_events, key=lambda x: x["detectedDateTime"])
                last_event_datetime = isoparse(last_event["detectedDateTime"])

                if last_event_datetime > most_recent_date_seen:
                    most_recent_date_seen = self.get_upper_second(last_event_datetime)

                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen
            self.cursor.offset = self.from_date

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL).set(
            int(current_lag.total_seconds())
        )
