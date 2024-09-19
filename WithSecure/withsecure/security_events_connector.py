import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Optional

import orjson
import requests
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON
from tenacity import Retrying, stop_after_attempt, wait_exponential

from withsecure import WithSecureModule
from withsecure.client import ApiClient
from withsecure.constants import API_FETCH_EVENTS_PAGE_SIZE, API_SECURITY_EVENTS_URL, API_TIMEOUT
from withsecure.helpers import human_readable_api_exception
from withsecure.logging import get_logger
from withsecure.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class FetchEventsException(Exception):
    pass


class SecurityEventsConnectorConfiguration(DefaultConnectorConfiguration):
    organization_id: str | None = Field(
        None, description="UUID of the organization (if missing, default org. is used)"
    )
    frequency: int = 60


class SecurityEventsConnector(Connector):
    """
    This connector fetches security events from the API of WithSecure
    """

    module: WithSecureModule
    configuration: SecurityEventsConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.most_recent_date_seen

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")
            # if undefined, retrieve events from the last minute
            if most_recent_date_seen_str is None:
                return now - timedelta(minutes=1)

            # parse the most recent date seen
            most_recent_date_seen = datetime.fromisoformat(most_recent_date_seen_str)

            return most_recent_date_seen

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            client_id=self.module.configuration.client_id,
            secret=self.module.configuration.secret,
            scope="connect.api.read",
            stop_event=self._stop_event,
            log_cb=self.log,
        )

    def __get_events(self, data: dict[str, Any], headers: dict[str, str]) -> requests.Response:
        for attempt in Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        ):
            with attempt:
                response: requests.Response = self.client.post(
                    API_SECURITY_EVENTS_URL, data=data, timeout=API_TIMEOUT, headers=headers
                )

        return response

    def __fetch_next_events(self, from_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        """
        Fetch all the events that occurred after the specified from date
        """
        # Create body of request
        # More information is here:
        # https://connect.withsecure.com/api-reference/elements#post-/security-events/v1/security-events
        data: dict[str, Any] = {
            "persistenceTimestampStart": from_date.isoformat(),
            "exclusiveStart": True,
            "limit": API_FETCH_EVENTS_PAGE_SIZE,
            "order": "asc",
            "engineGroup": ["epp", "edr", "ecp"],
            "organizationId": self.configuration.organization_id,
        }

        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.__get_events(data=data, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except Exception as any_exception:
            raise FetchEventsException(human_readable_api_exception(any_exception))

        while not self._stop_event.is_set():
            events = payload.get("items", [])

            # yielding events if defined
            if events:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                yield events
            else:
                logger.info(
                    f"The last page of events was empty. Waiting {self.configuration.frequency}s "
                    "before fetching next page"
                )
                # if no new events, we are up to date
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)
                time.sleep(self.configuration.frequency)

            anchor = payload.get("nextAnchor")
            if not anchor:
                return
            data["anchor"] = anchor
            try:
                response = self.__get_events(data=data, headers=headers)
                response.raise_for_status()
                payload = response.json()
            except Exception as any_exception:
                raise FetchEventsException(human_readable_api_exception(any_exception))

    def fetch_events(self) -> Generator[list[dict[str, Any]], None, None]:
        most_recent_date_seen = self.from_date

        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    last_event_date = datetime.fromisoformat(next_events[-1]["persistenceTimestamp"])

                    # save the greater date ever seen
                    if last_event_date > most_recent_date_seen:
                        most_recent_date_seen = last_event_date

                    # forward current events
                    yield next_events
        except FetchEventsException as fetch_error:
            self.log(human_readable_api_exception(fetch_error), level="error")

        # save the most recent date
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen

            # save in context the most recent date seen
            with self.context as cache:
                cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

            # Update the current lag only if the most_recent_date_seen was updated
            now = datetime.now(timezone.utc)
            current_lag = now - most_recent_date_seen
            EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # push events
            if batch_of_events:
                self.log(
                    message=f"{len(batch_of_events)} events collected",
                    level="info",
                )
                self.push_events_to_intakes(events=batch_of_events)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching WithSecure security events", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
