from datetime import datetime, timedelta, timezone
from typing import Generator
from urllib.parse import urljoin

from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointDatetime

from . import TrendMicroModule
from .metrics import EVENTS_LAG, INCOMING_MESSAGES
from .trigger_vision_one_base import TrendMicroVisionOneBaseConfiguration, TrendMicroVisionOneBaseConnector


class TrendMicroVisionOneOATConnectorConfiguration(TrendMicroVisionOneBaseConfiguration):
    filter: str | None = Field(None, description="Filter for events", max_length=4000)


class TrendMicroVisionOneOATConnector(TrendMicroVisionOneBaseConnector):
    CONNECTOR_TITLE = "Trend Micro Vision One OAT"
    CONNECTOR_METRICS_LABEL = "vision_one_oat"

    module: TrendMicroModule
    configuration: TrendMicroVisionOneOATConnectorConfiguration  # type: ignore[override]

    @property
    def typed_configuration(self) -> TrendMicroVisionOneOATConnectorConfiguration:
        return TrendMicroVisionOneOATConnectorConfiguration.model_validate(self.configuration)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._data_path is None:
            raise ValueError("data_path is required for checkpoint initialization")

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
        if self.typed_configuration.filter is not None:
            headers = {"TMV1-Filter": self.typed_configuration.filter}

        else:
            headers = {}

        url = urljoin(self.typed_configuration.base_url, "v3.0/oat/detections")
        response = self.client.get(url, params=query_params, headers=headers, timeout=60)

        while self.running:  # pragma: no cover
            self.handle_response_error(response)

            message = response.json()
            events = message.get("items", [])

            if events:
                INCOMING_MESSAGES.labels(
                    intake_key=self.typed_configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
                ).inc(len(events))
                yield events

            else:
                EVENTS_LAG.labels(
                    intake_key=self.typed_configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL
                ).set(0)
                return

            url = message.get("nextLink")
            if url is None:
                return

            response = self.client.get(url, timeout=60)

    def fetch_events(self) -> Generator[list, None, None]:
        initial_from_date = self.from_date
        most_recent_date_seen = self.sanitize_from_date(self.from_date)
        if most_recent_date_seen != self.from_date:
            self.reset_cursor_offset(most_recent_date_seen)
            self.from_date = most_recent_date_seen

        total_events_fetched = 0
        for next_events in self.__fetch_events(most_recent_date_seen):
            if next_events:
                total_events_fetched += len(next_events)
                last_event = max(next_events, key=lambda x: x["detectedDateTime"])
                last_event_datetime = isoparse(last_event["detectedDateTime"])

                if last_event_datetime > most_recent_date_seen:
                    most_recent_date_seen = self.get_upper_second(last_event_datetime)

                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_date:  # pragma: no cover
            self.from_date = most_recent_date_seen
            self.reset_cursor_offset(self.from_date)

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        current_lag_seconds = int(current_lag.total_seconds())
        EVENTS_LAG.labels(intake_key=self.typed_configuration.intake_key, type=self.CONNECTOR_METRICS_LABEL).set(
            current_lag_seconds
        )
        self.log(
            (
                "Fetch cycle completed "
                f"connector={self.CONNECTOR_METRICS_LABEL} "
                f"events_fetched_total={total_events_fetched} "
                f"initial_checkpoint={initial_from_date.isoformat()} "
                f"updated_checkpoint={most_recent_date_seen.isoformat()} "
                f"lag_seconds={current_lag_seconds}"
            ),
            level="debug",
        )
