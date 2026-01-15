import json
import time
from datetime import datetime, timedelta, timezone

from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from usta_modules.models import UstaATPModuleConfiguration, UstaModule
from usta_modules.usta_sdk import UstaAPIError, UstaClient


class UstaAtpConnector(Connector):
    """
    Simple Sekoia.io connector that:
      - Fetches compromised credentials tickets from USTA
      - Uses `created` as the cursor
      - Forwards raw JSON events to the intake
    No extras, retries, metrics, or optionals.
    """

    module = UstaModule
    configuration: UstaATPModuleConfiguration

    # The run method is called by Sekoia when launching the connector
    def run(self) -> None:
        # The log method is used to trace logs in the Connector logs of the Sekoia interface
        self.log(
            message=f"Start fetching events - running={self.running}", level="info"
        )

        if (
            self.module.configuration.api_key is None
            or self.module.configuration.api_key == ""
        ):
            self.log(message="API key not initialized!", level="critical")
            return
        if self.configuration.polling_interval is None:
            self.log(message="Polling interval not initialized!", level="critical")
            return

        usta_cli = UstaClient(token=self.module.configuration.api_key)
        date_cursor = datetime.now(timezone.utc) - timedelta(
            days=self.configuration.max_historical_days
        )
        # Iterate until the Connector is shut down by Sekoia
        while self.running:
            self.log(message="Polling USTA security intelligence API...", level="info")
            collected_events = []
            self.log(message=f"Polling events since: {date_cursor}", level="info")

            try:
                for event in usta_cli.iter_compromised_credentials(
                    start=date_cursor.isoformat()
                ):
                    collected_events.append(json.dumps(event))
            except UstaAPIError as e:
                self.log(message=f"USTA-SDK Error: {e}", level="error")

            # Push events to Sekoia platform
            if collected_events:
                date_cursor = datetime.now(timezone.utc)
                self.log(
                    message=f"{len(collected_events)} events collected",
                    level="info",
                )

            # Ingest the collected events in Sekoia
            if len(collected_events) > 0:
                self.push_events_to_intakes(events=collected_events)
                self.log(message="Events pushed to intakes!", level="info")
            time.sleep(self.configuration.polling_interval)
