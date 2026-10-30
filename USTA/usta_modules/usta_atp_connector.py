import json
import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector

from .models import UstaATPConnectorConfiguration, UstaModule
from .usta_sdk import UstaAPIError, UstaAuthenticationError, UstaClient


def parse_created(value: Any) -> datetime | None:
    """Parse the `created` field of an event into an aware UTC datetime (None if invalid)."""
    if not isinstance(value, str):
        return None
    try:
        created = datetime.fromisoformat(value)
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return created.astimezone(UTC)


class UstaAtpConnector(Connector):
    """
    Simple Sekoia.io connector that:
      - Fetches compromised credentials tickets from USTA
      - Uses `created` as the cursor, persisted in the connector data path
      - Forwards raw JSON events to the intake
    No extras, retries, metrics, or optionals.
    """

    module = UstaModule
    configuration: UstaATPConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # The `start` filter is inclusive: remember the ids of the events created at the cursor
        # to not forward them twice
        self._boundary_ids: set[Any] = set()

    @cached_property
    def cursor(self) -> CheckpointDatetime:
        max_historical = timedelta(days=self.configuration.max_historical_days)
        return CheckpointDatetime(path=self.data_path, start_at=max_historical, ignore_older_than=max_historical)

    # The run method is called by Sekoia when launching the connector
    def run(self) -> None:
        # The log method is used to trace logs in the Connector logs of the Sekoia interface
        self.log(message=f"Start fetching events - running={self.running}", level="info")

        usta_cli = UstaClient(token=self.module.configuration.api_key)
        # Iterate until the Connector is shut down by Sekoia
        while self.running:
            self.log(message="Polling USTA security intelligence API...", level="info")
            collected_events = []
            date_cursor: datetime = self.cursor.offset
            most_recent_created = date_cursor
            most_recent_ids = set(self._boundary_ids)
            self.log(message=f"Polling events since: {date_cursor}", level="info")

            try:
                for event in usta_cli.iter_compromised_credentials(
                    start=date_cursor.isoformat(), ordering=["created"]
                ):
                    event_id = event.get("id")
                    created = parse_created(event.get("created"))
                    if event_id is not None and event_id in self._boundary_ids and created == date_cursor:
                        continue

                    collected_events.append(json.dumps(event))

                    if created is not None and created > most_recent_created:
                        most_recent_created = created
                        most_recent_ids = set()
                    if created == most_recent_created and event_id is not None:
                        most_recent_ids.add(event_id)
            except UstaAuthenticationError as e:
                self.log(message=f"USTA Authentication Error: {e!s}", level="critical")
                raise e
            except UstaAPIError as e:
                self.log(message=f"USTA-SDK Error: {e}", level="error")

            # Push events to Sekoia platform
            if collected_events:
                self.log(
                    message=f"{len(collected_events)} events collected",
                    level="info",
                )

            # Ingest the collected events in Sekoia
            if len(collected_events) > 0:
                self.push_events_to_intakes(events=collected_events)
                self.log(message="Events pushed to intakes!", level="info")

                # Move the cursor only once the events are forwarded
                self.cursor.offset = most_recent_created
                self._boundary_ids = most_recent_ids
            time.sleep(self.configuration.frequency)
