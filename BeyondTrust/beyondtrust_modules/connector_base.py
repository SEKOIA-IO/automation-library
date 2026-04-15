import time
from abc import abstractmethod
from functools import cached_property
from typing import Generator

import orjson
import requests
from sekoia_automation.connector import Connector

from . import BeyondTrustModule
from .client import ApiClient
from .logging import get_logger
from .metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

logger = get_logger()


class BeyondTrustBaseConnector(Connector):
    module: BeyondTrustModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    def _handle_response_error(self, response: requests.Response) -> bool:
        if not response.ok:
            level = "critical" if response.status_code in [401, 403] else "error"

            message = f"Request to BeyondTrust API failed with status {response.status_code} - {response.reason}"

            try:
                error = response.json()
                logger.error(
                    message,
                    error_message=error.get("message"),
                    error_number=error.get("number"),
                )
            except Exception:
                pass

            self.log(message=message, level=level)

        return not response.ok

    def _check_xml_error(self, response: requests.Response) -> bool:
        """Check for XML error in a 200 response. Returns True if error found."""
        if "<error" in response.text and response.status_code == 200:
            self.log(f"An error occurred. response: {response.text}", level="error")
            return True

        return False

    @abstractmethod
    def fetch_events(self) -> Generator[list, None, None]:
        raise NotImplementedError

    def next_batch(self):
        batch_start_time = time.time()

        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
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

    def run(self) -> None:  # pragma: no cover
        self.log(message="Start fetching BeyondTrust events", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
