from datetime import datetime, timedelta, timezone
from typing import Generator

from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import DefaultConnectorConfiguration

from . import BeyondTrustModule
from .connector_base import BeyondTrustBaseConnector
from .helpers import parse_vault_activity
from .metrics import EVENTS_LAG


class BeyondTrustPRAVaultAccountActivityConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(300, description="Batch frequency in seconds")


class BeyondTrustPRAVaultAccountActivityConnector(BeyondTrustBaseConnector):
    module: BeyondTrustModule
    configuration: BeyondTrustPRAVaultAccountActivityConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            time_unit=TimeUnit.SECOND,
            path=self.data_path,
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=7),
        )
        self.from_date = self.cursor.offset

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date
        self.log(
            f"Fetching events from {most_recent_date_seen} ({datetime.fromtimestamp(most_recent_date_seen, tz=timezone.utc)})",
            level="info",
        )

        response = self.client.get_vault_activity(end_time=most_recent_date_seen)
        if self._handle_response_error(response):
            return

        if response.ok and "<error" in response.text:
            if "No vault account activity matching your chosen criteria is available" in response.text:
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                # Just no new events
                return

            self.log(f"An error occurred. response: {response.text}", level="error")
            return

        events = parse_vault_activity(response.content)
        if len(events) > 0:
            yield events

        else:
            return

        latest_event_timestamp = max(int(event["timestamp"]) for event in events)
        if latest_event_timestamp > most_recent_date_seen:
            self.from_date = latest_event_timestamp
            self.cursor.offset = latest_event_timestamp

            now = int(datetime.now(timezone.utc).timestamp())
            current_lag = now - latest_event_timestamp
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)
