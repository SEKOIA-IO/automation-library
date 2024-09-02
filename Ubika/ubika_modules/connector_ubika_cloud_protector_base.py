import signal
import time
from abc import abstractmethod
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from threading import Event

import orjson
import requests
from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import UbikaModule
from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FetchEventsException(Exception):
    pass


class UbikaCloudProtectorConnectorConfiguration(DefaultConnectorConfiguration):
    provider: str = Field(..., description="Id of cirrus provider")
    tenant: str = Field(..., description="Id of cirrus tenant")
    token: str = Field(..., description="API token", secret=True)

    frequency: int = 60
    chunk_size: int = 1000


class UbikaCloudProtectorBaseConnector(Connector):
    module: UbikaModule
    configuration: UbikaCloudProtectorConnectorConfiguration

    BASE_URI = "https://eu-west-2.cloudprotector.com/api/v1"
    NAME = "Ubika Cloud Protector"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.most_recent_date_seen

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, _, __) -> None:
        self.log(message=f"Stopping {self.NAME} connector", level="info")  # pragma: no cover
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

        # if undefined, retrieve events from the last hour
        if most_recent_date_seen_str is None:
            return now - timedelta(hours=1)

        # parse the most recent date seen
        most_recent_date_seen = isoparse(most_recent_date_seen_str)

        # we don't retrieve messages older than one week
        one_week_ago = now - timedelta(days=7)
        if most_recent_date_seen < one_week_ago:
            most_recent_date_seen = one_week_ago

        return most_recent_date_seen

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            self.configuration.token,
        )

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = (
                f"Request on {self.NAME} API to fetch events failed with status "
                f"{response.status_code} - {response.reason} on {response.request.url}"
            )

            raise FetchEventsException(message)

    @abstractmethod
    def generate_endpoint_url(self) -> str:
        raise NotImplementedError

    def __fetch_next_events(self, from_date: datetime) -> Generator[list, None, None]:
        # get the first page of events
        headers = {"Content-Type": "application/json"}
        # url = f"{self.BASE_URI}/providers/{self.configuration.provider}/tenants/{self.configuration.tenant}/alertlogs"
        url = self.generate_endpoint_url()
        params = {
            "start_time": int(from_date.timestamp()),
            "limit": self.configuration.chunk_size,
        }

        response = self.client.get(url, params=params, headers=headers, timeout=60)

        while self.running:
            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            data = response.json()
            events = data["items"]

            # yielding events if defined
            if data and len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                yield events

            else:
                self.log(
                    message="The last page of events was empty.",
                    level="info",
                )  # pragma: no cover
                return

            cursor = data.get("cursor")
            if cursor is None:
                return

            response = self.client.get(
                url,
                params={"cursor": cursor, "limit": self.configuration.chunk_size},
                headers=headers,
                timeout=60,
            )

    @staticmethod
    def get_upper_second(time: datetime) -> datetime:
        """
        Return the upper second from a datetime

        :param datetime time: The starting datetime
        :return: The upper second of the starting datetime
        :rtype: datetime
        """
        return (time + timedelta(seconds=1)).replace(microsecond=0)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date
        current_lag: int = 0

        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    # save the greatest date ever seen
                    last_event = max(next_events, key=lambda x: x["timestamp"])
                    last_event_timestamp = last_event["timestamp"]
                    last_event_datetime = datetime.fromtimestamp(last_event_timestamp).astimezone(timezone.utc)

                    if last_event_datetime > most_recent_date_seen:
                        most_recent_date_seen = self.get_upper_second(last_event_datetime)

                    yield next_events
        finally:
            # save the most recent date
            if most_recent_date_seen > self.from_date:
                self.from_date = most_recent_date_seen

                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

                delta_time = datetime.now(timezone.utc) - most_recent_date_seen
                current_lag = int(delta_time.total_seconds())

        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )  # pragma: no cover
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )  # pragma: no cover

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )  # pragma: no cover
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="debug",
            )  # pragma: no cover
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message=f"Start fetching {self.NAME} events", level="info")  # pragma: no cover

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")  # pragma: no cover
