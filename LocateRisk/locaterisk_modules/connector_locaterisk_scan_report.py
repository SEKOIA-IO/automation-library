import csv
import io
import json
import time

from pydantic import Field
import requests
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import LocateRiskModule


class LocateRiskScanReportConnectorConfiguration(DefaultConnectorConfiguration):
    polling_interval: int = Field(5, description="Polling interval in minutes")


class LocateRiskScanReportConnector(Connector):
    module: LocateRiskModule
    configuration: LocateRiskScanReportConnectorConfiguration

    def run(self):
        self.log(message="Start fetching events", level="info")

        while self.running:
            self.log("Polling LocateRisk API...", level="info")

            batch_of_events = []
            try:
                response = requests.get(
                    f"{self.module.configuration.report_url}/{self.module.configuration.scan_id}/csv",
                    headers={"Authorization": f"Bearer {self.module.configuration.api_key}"},
                    timeout=60,
                )

                response.raise_for_status()
                response.encoding = "utf-8-sig"  # handle UTF-8 BOM if present

                # csv.DictReader correctly handles quoted multi-line fields
                # (e.g. CVE lists with embedded newlines)
                reader = csv.DictReader(
                    io.StringIO(response.text),
                    delimiter=";",
                    quotechar='"',
                )

                for row in reader:
                    # Skip completely empty rows
                    if not any(value and value.strip() for value in row.values()):
                        continue

                    row["source"] = "locaterisk"
                    batch_of_events.append(json.dumps(row))

            except requests.RequestException as error:
                self.log_exception(error, message="Error fetching data from LocateRisk API")
            except csv.Error as error:
                self.log_exception(error, message="Error parsing CSV from LocateRisk API")

            if batch_of_events:
                self.log(message=f"{len(batch_of_events)} events collected", level="info")
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log("No events to push this cycle", level="info")

            time.sleep(self.configuration.polling_interval * 60)
