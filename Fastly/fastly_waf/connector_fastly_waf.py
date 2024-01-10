import datetime
import time
from functools import cached_property
from typing import Generator

import orjson
from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FastlyWAFConnectorConfiguration(DefaultConnectorConfiguration):
    email: str = Field(..., description="User's email")
    token: str = Field(..., description="API token")
    corp: str = Field(..., description="Corporation name", pattern=r"^[0-9a-z_.-]+$")
    site: str = Field(..., description="Site name", pattern=r"^[0-9a-z_.-]+$")

    frequency: int = 60
    chunk_size: int = 1000


class FastlyWAFConnector(Connector):
    base_uri = "https://dashboard.signalsciences.net"
    configuration: FastlyWAFConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.from_datetime = self.most_recent_date_seen

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(email=self.configuration.email, token=self.configuration.token)

    @property
    def most_recent_date_seen(self) -> datetime.datetime:
        now = datetime.datetime.now(datetime.timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

        # if undefined, retrieve events from the last minute
        if most_recent_date_seen_str is None:
            return now - datetime.timedelta(minutes=1)

        # parse the most recent date seen
        most_recent_date_seen = isoparse(most_recent_date_seen_str)

        # We don't retrieve messages older than one week
        one_week_ago = now - datetime.timedelta(days=7)
        if most_recent_date_seen < one_week_ago:
            most_recent_date_seen = one_week_ago

        return most_recent_date_seen

    def save_checkpoint(self, ts: int) -> None:
        with self.context as cache:
            cache["most_recent_date_seen"] = ts

    def __fetch_next_events(self, from_datetime: datetime.datetime) -> Generator[list, None, None]:
        from_timestamp = int(from_datetime.timestamp())
        next_url = (
            f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites/{self.configuration.site}/events?"
            f"sort=asc&limit={self.configuration.chunk_size}&from={from_timestamp}"
        )

        while self.running:
            response = self.client.get(url=next_url, timeout=60)
            response_content = response.json()

            events = response_content["data"]
            if events:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events))
                yield events

            else:
                self.log(
                    message=f"The last page of events was empty. "
                    f"Waiting {self.configuration.frequency} seconds before fetching next page",
                    level="info",
                )
                time.sleep(self.configuration.frequency)

            next_path = response_content.get("next", {}).get("uri")
            if not next_path:
                return

            next_url = "%s/%s" % (self.base_uri, next_path)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_datetime
        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    last_event_datetime = isoparse(next_events[-1]["timestamp"])
                    if last_event_datetime > most_recent_date_seen:
                        most_recent_date_seen = (last_event_datetime + datetime.timedelta(seconds=1)).replace(
                            microsecond=0
                        )

                    yield next_events

        finally:
            # save the most recent date
            if most_recent_date_seen > self.from_datetime:
                self.from_datetime = most_recent_date_seen

                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_seen"] = self.from_datetime.isoformat()

        now = datetime.datetime.now(datetime.timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(int(current_lag.total_seconds()))

    def next_batch(self):
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
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"Next batch in the future. Waiting {delta_sleep} seconds",
                level="debug",
            )
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching Fastly WAF events", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
