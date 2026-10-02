import csv
import hashlib
import io
import json
import time

import requests
from pydantic import Field, field_validator
from requests.adapters import HTTPAdapter
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from urllib3.util.retry import Retry

from . import LocateRiskModule
from .metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class LocateRiskScanReportConnectorConfiguration(DefaultConnectorConfiguration):
    """Connector-specific configuration for the LocateRisk scan report poller."""

    polling_interval: int = Field(5, description="Polling interval in minutes")
    scan_id: str = Field(..., description="Scan ID", json_schema_extra={"secret": True})
    report_url: str = Field(
        "https://app.locaterisk.com/api/rest/report/export",
        description="Report export URL used to fetch scan findings",
    )

    @field_validator("report_url")
    @classmethod
    def _require_https_report_url(cls, value: str) -> str:
        if not value.lower().startswith("https://"):
            raise ValueError("report_url must use HTTPS")
        return value


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
        # Persisted checkpoint: content hashes of the rows forwarded on the last
        # successful poll, so unchanged rows are not pushed again on every cycle.
        self.context = PersistentJSON("context.json", self._data_path)

    def _build_report_url(self) -> str:
        """Build the CSV report URL for the configured scan."""
        return f"{self.configuration.report_url.rstrip('/')}/{self.configuration.scan_id}/csv"

    @staticmethod
    def _row_hash(row: dict) -> str:
        """Stable content hash of a report row, independent of column ordering."""
        return hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()

    def _load_seen_hashes(self) -> set[str]:
        """Load the row hashes forwarded on the previous poll."""
        with self.context as cache:
            return set(cache.get("seen_row_hashes", []))

    def _save_seen_hashes(self, hashes: set[str]) -> None:
        """Persist the set of row hashes present in the current report."""
        with self.context as cache:
            cache["seen_row_hashes"] = sorted(hashes)

    def run(self) -> None:
        """Poll the LocateRisk report export on an interval and forward CSV rows as events."""
        self.log(message="Start fetching events", level="info")

        while self.running:
            self.log("Polling LocateRisk API...", level="info")
            batch_start_time = time.time()

            had_error = False
            batch_of_events = []
            current_hashes: set[str] = set()
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

                seen_hashes = self._load_seen_hashes()

                for row in reader:
                    # Skip completely empty rows
                    if not any(value and value.strip() for value in row.values()):
                        continue

                    row["source"] = "locaterisk"
                    row_hash = self._row_hash(row)
                    current_hashes.add(row_hash)

                    # The report is a full snapshot re-fetched every poll; only
                    # forward rows we have not already pushed in a prior cycle.
                    if row_hash in seen_hashes:
                        continue

                    batch_of_events.append(json.dumps(row))

            except requests.RequestException as error:
                had_error = True
                self.log_exception(error, message="Error fetching data from LocateRisk API")
            except csv.Error as error:
                had_error = True
                self.log_exception(error, message="Error parsing CSV from LocateRisk API")

            if batch_of_events:
                self.log(message=f"{len(batch_of_events)} events collected", level="info")
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
            elif not had_error:
                self.log("No new events to push this cycle", level="info")

            # Checkpoint the rows present in this report (only on a clean fetch), so
            # rows that dropped out of the report are forgotten and unchanged rows
            # are not re-sent next cycle.
            if not had_error:
                self._save_seen_hashes(current_hashes)

            batch_duration = time.time() - batch_start_time
            FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

            self._stop_event.wait(timeout=self.configuration.polling_interval * 60)
