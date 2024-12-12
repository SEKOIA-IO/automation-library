from datetime import datetime, timedelta, timezone
from typing import Generator
from urllib.parse import urljoin

from dateutil.parser import isoparse
from sekoia_automation.checkpoint import CheckpointDatetime

from . import TrendMicroModule
from .logging import get_logger
from .metrics import EVENTS_LAG, INCOMING_MESSAGES
from .trigger_vision_one_base import TrendMicroVisionOneBaseConfiguration, TrendMicroVisionOneBaseConnector

logger = get_logger()


class TrendMicroVisionOneWorkbenchConnectorConfiguration(TrendMicroVisionOneBaseConfiguration):
    pass


class TrendMicroVisionOneWorkbenchConnector(TrendMicroVisionOneBaseConnector):
    CONNECTOR_TITLE = "Trend Micro Vision One Workbench Alerts"
    CONNECTOR_METRICS_LABEL = "vision_one_workbench"

    module: TrendMicroModule
    configuration: TrendMicroVisionOneWorkbenchConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path, start_at=timedelta(minutes=1), ignore_older_than=timedelta(hours=1)
        )
        self.from_date = self.cursor.offset

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
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL).set(
            int(current_lag.total_seconds())
        )
