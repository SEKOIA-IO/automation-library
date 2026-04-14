import tempfile
import time
import zipfile
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import DefaultConnectorConfiguration

from . import BeyondTrustModule
from .connector_base import BeyondTrustBaseConnector
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from .syslog_helpers import extract_when_timestamp, iter_reassembled_records


class BeyondTrustPRASyslogConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(30 * 60, description="Batch frequency in seconds")


class BeyondTrustPRASyslogConnector(BeyondTrustBaseConnector):
    module: BeyondTrustModule
    configuration: BeyondTrustPRASyslogConfiguration

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointTimestamp(
            time_unit=TimeUnit.SECOND,
            path=self._data_path,
            start_at=timedelta(days=30),
            ignore_older_than=timedelta(days=30),
        )
        self.from_date = self.cursor.offset

    def _download_syslog_zip(self) -> Path | None:
        """
        Fetch syslog ZIP from BeyondTrust API and save to a temp file.

        Based on official documentation we get a zip file in case of success.
        Otherwise in case of errors we get xml

        Docs:
            https://docs.beyondtrust.com/rs/reference/reporting-api#syslog
        """
        response = self.client.get_syslog()

        if self._handle_response_error(response):
            return None

        # For XML error responses, check Content-Type before saving binary
        content_type = response.headers.get("Content-Type", "").lower()
        if "xml" in content_type or "text" in content_type:
            if self._check_xml_error(response):
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)

                return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            return tmp_path

    def _iter_syslog_lines(self, zip_path: Path) -> Generator[str, None, None]:
        """Yield lines lazily from all files inside the ZIP."""
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                with zf.open(name) as f:
                    for raw_line in f:
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                        if line:
                            yield line

    def fetch_events(self) -> Generator[list, None, None]:
        zip_path = None
        try:
            zip_path = self._download_syslog_zip()
            if zip_path is None:
                return

            try:
                lines = self._iter_syslog_lines(zip_path)
                payloads = iter_reassembled_records(lines)

                most_recent_timestamp = self.from_date
                events_batch: list[str] = []

                for payload in payloads:
                    when_ts = extract_when_timestamp(payload)
                    if when_ts is None:
                        continue
                    if when_ts <= self.from_date:
                        continue

                    events_batch.append(payload)
                    INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc()

                    if when_ts > most_recent_timestamp:
                        most_recent_timestamp = when_ts

                    if len(events_batch) >= 1000:
                        yield events_batch
                        events_batch = []

                if events_batch:
                    yield events_batch

                if most_recent_timestamp > self.from_date:
                    self.from_date = most_recent_timestamp
                    self.cursor.offset = most_recent_timestamp

                    now = int(datetime.now(timezone.utc).timestamp())
                    current_lag = now - most_recent_timestamp
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)
            except zipfile.BadZipFile:
                self.log("Downloaded content is not a valid ZIP archive", level="warning")
                return

        finally:
            if zip_path is not None and zip_path.exists():
                zip_path.unlink()

    def next_batch(self):
        """Override to push raw string events instead of JSON-serialized dicts."""
        batch_start_time = time.time()

        for events in self.fetch_events():
            if len(events) > 0:
                self.log(
                    message=f"Forwarded {len(events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                self.push_events_to_intakes(events=events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(message=f"Fetched and forwarded events in {batch_duration} seconds", level="info")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)
