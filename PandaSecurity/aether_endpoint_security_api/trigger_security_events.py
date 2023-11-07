import collections
import time
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta
from functools import cached_property
from typing import Deque

import requests
from sekoia_automation.trigger import Trigger

from aether_endpoint_security_api.base import AuthorizationMixin

EVENT_TYPES = {
    1: "Malware",
    2: "PUPs (Potentially Unwanted Programs)",
    3: "Blocked Programs",
    4: "Exploits",
    5: "Blocked by Advanced Security",
    6: "Virus",
    7: "Spyware",
    8: "Hacking Tools and PUPs detected by Antivirus",
    9: "Phishing",
    10: "Suspicious",
    11: "Dangerous Actions",
    12: "Tracking Cookies",
    13: "Malware URLs",
    14: "Other security event by Antivirus",
    15: "Intrusion Attempts",
    16: "Blocked Connections",
    17: "Blocked Devices",
    18: "Indicators of Attack",
}


class AetherSecurityEventsTrigger(Trigger, AuthorizationMixin):
    RFC3339_STRICT_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_credentials: dict | None = None
        self.http_session: requests.Session = requests.Session()

        self.last_message_date: dict[int, str] = {
            event_type: (datetime.utcnow() - timedelta(minutes=1)).strftime(self.RFC3339_STRICT_FORMAT)
            for event_type in EVENT_TYPES.keys()
        }
        self.max_batch_size = 500

    def run(self):
        self.log(message="WatchGuard Aether Events Trigger has started", level="info")

        while True:
            try:
                self._fetch_events()
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.configuration["frequency"])

    def _fetch_events(self) -> None:
        """
        Successively queries the watchguard aether events pages while more are available
        and the current batch is not too big.
        """
        for event_type, event_type_name in EVENT_TYPES.items():
            message_batch: Deque[dict] = collections.deque()
            has_more_message = True

            last_message_date = self.last_message_date[event_type]

            self.log(
                message=f"Fetching recent Aether '{event_type_name}' messages since {last_message_date}",
                level="info",
            )

            while has_more_message:
                has_more_message = False
                next_events = self._fetch_next_events(last_message_date=last_message_date, event_type=event_type)
                if next_events:
                    last_message_date = self._get_event_date(next_events[-1])
                    message_batch.extend(next_events)
                    has_more_message = True

                if len(message_batch) >= self.max_batch_size:
                    break

            if message_batch:
                self.log(
                    message=f"Send a batch of {len(message_batch)} {event_type} messages",
                    level="info",
                )

                self.send_event(
                    event_name=f"Aether-events_{last_message_date}",
                    event={"events": list(message_batch)},
                )

            self.log(
                message=f"Set last_message_date for Aether '{event_type_name}' to {last_message_date}",
                level="info",
            )
            self.last_message_date[event_type] = last_message_date

    def _get_event_date(self, event: dict) -> str:
        """
        Extract a value from several fields of the event
        """
        candidates = ("security_event_date", "date")

        for candidate in candidates:
            if candidate in event:
                return str(event[candidate])

        raise ValueError("Cannot extract date from event")

    def _filter_events(self, events: Sequence, last_message_date: str) -> Generator[dict, None, None]:
        """
        Return only the events greater than the last_message_date
        """
        for event in events:
            # get only the last events (discard already processed events)
            if self._get_event_date(event) > last_message_date:
                yield event

    def _enrich_event(self, events: Generator, event_type: int) -> Generator[dict, None, None]:
        """
        Add some additional information in the event
        """
        for event in events:
            event["security_event_type"] = event_type
            yield event

    def _fetch_next_events(self, last_message_date: str, event_type: int) -> list[dict]:
        """
        Returns the next page of events produced by WatchGuard Aether
        """
        if event_type not in EVENT_TYPES:
            raise TypeError

        response = self.http_session.get(
            url=(
                f"{self.module.configuration['base_url']}/rest/aether-endpoint-security/aether-mgmt/api/v1/accounts/"
                f"{self.module.configuration['account_id']}/securityevents/{event_type}/export/1"
            ),
            headers={
                **self._http_default_headers,
                "Accept": "application/json",
                "Authorization": self._get_authorization(),
                "WatchGuard-API-Key": self.module.configuration["api_key"],
                "Content-Type": "application/json",
            },
        )
        if not response.ok:
            self.log(
                message=(
                    f"Request on Aether API to fetch events of tenant {self.module.configuration['account_id']} "
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level="error",
            )

            return []
        else:
            content = response.json()
            if content is None:
                return []

            events = self._filter_events(content.get("data", []), last_message_date)
            events = self._enrich_event(events, event_type)
            return list(events)
