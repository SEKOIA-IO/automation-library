import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import requests
from pydantic import Field
from requests.exceptions import HTTPError
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from secuserve_modules import SecuserveModule
from secuserve_modules.metrics import (
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
)

# The API never exposes events more recent than `now - PUBLICATION_DELAY`: filtering
# results need a couple of minutes to reach the database the API reads from.
PUBLICATION_DELAY = timedelta(seconds=120)

# The API caps the requested period to one hour. A wider window is silently
# truncated, so the connector walks the backlog one hour at a time.
MAX_TIME_RANGE = timedelta(hours=1)

# Bounds of the period are inclusive on both ends: the next window starts one
# second after the last one so that events are not collected twice.
WINDOW_STEP = timedelta(seconds=1)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ESecuremailEventsConfiguration(DefaultConnectorConfiguration):
    api_key: str = Field(description="SIEM API key of the domain, found in the e-securemail console")
    frequency: int = Field(60, description="Batch frequency in seconds")
    chunk_size: int = Field(1000, description="Max size of chunks for batch processing")


class ESecuremailEventsConnector(Connector):
    """
    Collect the filtering events of a domain protected by SECUSERVE e-securemail.

    Quick notes
    - Authentication is a bearer token, the per-domain SIEM API key
    - The period is driven by the connector through the `interval` parameter, and the
      served upper bound comes back in the `X-Query-End-Time` response header
    - `format=flat` answers NDJSON, one event per recipient and per line
    """

    module: SecuserveModule
    configuration: ESecuremailEventsConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path,
            start_at=timedelta(minutes=5),
            ignore_older_than=timedelta(days=7),
        )

    @cached_property
    def api_url(self) -> str:
        return f"{self.module.configuration.api_host.rstrip('/')}/siem/suivi"

    @cached_property
    def http_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {self.configuration.api_key}"})
        return session

    def next_time_range(self) -> tuple[datetime, datetime] | None:
        """
        Return the next period to collect, or None when the cursor already reached
        the most recent events the API is willing to serve.
        """
        start = self.cursor.offset
        end = min(start + MAX_TIME_RANGE, datetime.now(UTC) - PUBLICATION_DELAY)

        if end <= start:
            return None

        return start, end

    def fetch_events(self, start: datetime, end: datetime) -> tuple[list[str], datetime]:
        """
        Collect the events of the period and return them with the upper bound the
        API actually served.
        """
        response = self.http_session.get(
            self.api_url,
            params={
                "format": "flat",
                "interval": f"{start.strftime(TIME_FORMAT)}/{end.strftime(TIME_FORMAT)}",
            },
            stream=True,
            timeout=120,
        )

        if response.status_code == 401:
            raise HTTPError(
                "Authentication failed: the SIEM API key is missing, invalid or the domain is disabled",
                response=response,
            )

        response.raise_for_status()

        events = [line.decode("utf-8") for line in response.iter_lines() if line]

        return events, self.served_end(response, end)

    @staticmethod
    def served_end(response: requests.Response, requested_end: datetime) -> datetime:
        """
        The API truncates the period it was asked for; `X-Query-End-Time` tells how
        far it actually went. Fall back on the requested bound when the header is
        absent or unreadable.
        """
        header = response.headers.get("X-Query-End-Time")
        if not header:
            return requested_end

        try:
            return datetime.fromtimestamp(int(header), tz=UTC)
        except ValueError:
            return requested_end

    def push_events(self, events: list[str]) -> None:
        for index in range(0, len(events), self.configuration.chunk_size):
            chunk = events[index : index + self.configuration.chunk_size]
            self.log(message=f"Forward {len(chunk)} events to the intake", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(chunk))
            self.push_events_to_intakes(events=chunk)

    def next_batch(self) -> bool:
        """
        Collect and forward the next period. Return True when the cursor is still
        behind and the next period can be collected right away.
        """
        time_range = self.next_time_range()
        if time_range is None:
            self.log(message="No new period to collect", level="info")
            return False

        start, end = time_range
        batch_start_time = time.time()

        events, served_end = self.fetch_events(start, end)
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))

        if events:
            self.push_events(events)
        else:
            self.log(message="No events to forward", level="info")

        self.cursor.offset = served_end + WINDOW_STEP

        lag = (datetime.now(UTC) - served_end).total_seconds()
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(lag))
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
            time.time() - batch_start_time
        )
        self.log(
            message=f"Collected {len(events)} events, lag is now {int(lag)} seconds",
            level="info",
        )

        # another full period is already available: collect it without waiting
        return datetime.now(UTC) - PUBLICATION_DELAY - self.cursor.offset >= MAX_TIME_RANGE

    def run(self) -> None:  # pragma: no cover
        self.log(message="e-securemail events connector has started", level="info")

        while self.running:
            try:
                # keep collecting without waiting as long as we lag behind
                while self.running and self.next_batch():
                    pass
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")

            time.sleep(self.configuration.frequency)

        self.log(message="e-securemail events connector has stopped", level="info")
