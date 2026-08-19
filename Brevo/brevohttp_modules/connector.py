import time
from brevo import Brevo
from brevo.core import ApiError, ParsingError
from datetime import datetime, timedelta
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import BrevoHttpModule
from .models import BrevoApiData


class BrevoConnectorConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(5, description="Polling interval in minutes")


class BrevoConnector(Connector):
    module: BrevoHttpModule
    configuration: BrevoConnectorConfiguration

    def run(self):
        self.log(message="Start fetching events", level="info")

        client = Brevo(
            api_key=self.module.configuration.api_key,
        )

        end_date = datetime.now()
        start_date = end_date - timedelta(minutes=5)

        while self.running:
            self.log("Polling Brevo API...", level="info")

            try:
                raw_data = client.account.get_account_activity(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    limit=100,
                ).json()

                data = BrevoApiData.model_validate_json(raw_data, strict=True)

                batch_of_events = list(
                    map(
                        lambda l: l.model_dump_json(),
                        data.logs,
                    )
                )

                # Push events to Sekoia platform
                if batch_of_events:
                    self.log(
                        message=f"{len(batch_of_events)} events collected",
                        level="info",
                    )
                    self.push_events_to_intakes(events=batch_of_events)
            except (ApiError, ParsingError) as error:
                self.log_exception(error, message="Error fetching data from Brevo API")

            # Wait for the next polling interval
            time.sleep(self.configuration.polling_interval * 60)
