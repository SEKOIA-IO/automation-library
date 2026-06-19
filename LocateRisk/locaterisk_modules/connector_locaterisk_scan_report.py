import csv
import io
import json

import requests
from pydantic import Field
from requests.adapters import HTTPAdapter
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from urllib3.util.retry import Retry

from . import LocateRiskModule


class LocateRiskScanReportConnectorConfiguration(DefaultConnectorConfiguration):
    """Connector-specific configuration for the LocateRisk scan report poller."""

    polling_interval: int = Field(5, description="Polling interval in minutes")


class LocateRiskScanReportConnector(Connector):
    """Periodically fetches a LocateRisk scan report (CSV) and forwards each row as an event."""

    module: LocateRiskModule
    configuration: LocateRiskScanReportConnectorConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _build_report_url(self) -> str:
        """Build the CSV report URL for the configured scan."""
        return f"{self.module.configuration.report_url}/{self.module.configuration.scan_id}/csv"

    def run(self) -> None:
        """Poll the LocateRisk report export on an interval and forward CSV rows as events."""
        self.log(message="Start fetching events", level="info")

        while self.running:
            self.log("Polling LocateRisk API...", level="info")

            had_error = False
            batch_of_events = []
            try:
                response = self._session.get(
                    self._build_report_url(),
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
                had_error = True
                self.log_exception(error, message="Error fetching data from LocateRisk API")
            except csv.Error as error:
                had_error = True
                self.log_exception(error, message="Error parsing CSV from LocateRisk API")

            if batch_of_events:
                self.log(message=f"{len(batch_of_events)} events collected", level="info")
                self.push_events_to_intakes(events=batch_of_events)
            elif not had_error:
                self.log("No events to push this cycle", level="info")

            self._stop_event.wait(timeout=self.configuration.polling_interval * 60)
