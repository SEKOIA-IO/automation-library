import time
from functools import cached_property
from typing import Generator
from posixpath import join as urljoin

import orjson
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import ExtraHopModule
from .client import ApiClient
from .client.auth import ExtraHopApiAuthentication
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class ExtraHopReveal360Configuration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000


class ExtraHopReveal360Connector(Connector):
    module: ExtraHopModule
    configuration: ExtraHopReveal360Configuration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.get_last_timestamp()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            auth=ExtraHopApiAuthentication(
                base_url=self.module.configuration.tenant_url,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )
        )

    def get_last_timestamp(self) -> int:
        now = int(time.time() * 1000)  # in milliseconds

        with self.context as cache:
            most_recent_ts_seen = cache.get("last_timestamp")

        one_week_ago = now - 7 * 24 * 60 * 60 * 1000

        # if undefined, retrieve events from the last 7 days
        if most_recent_ts_seen is None:
            return one_week_ago

        if most_recent_ts_seen < one_week_ago:
            most_recent_ts_seen = one_week_ago

        return most_recent_ts_seen

    def set_last_timestamp(self, last_timestamp: int) -> None:
        with self.context as cache:
            cache["last_timestamp"] = last_timestamp

    def fetch_page(self, from_time: int, offset: int) -> list[dict] | None:
        params = {
            "from": from_time,
            "limit": self.configuration.chunk_size,
            "offset": offset,
            "sort": [{"direction": "asc", "field": "start_time"}],
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = urljoin(self.module.configuration.tenant_url, "api/v1/detections/search")
        response = self.client.post(url, json=params, headers=headers, timeout=60)

        if not response.ok:
            self.log(
                message=(
                    f"Request on ExtraHop Reveal(x) 360 API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.reason}"
                ),
                level="error",
            )
            return None

        content = response.json() if len(response.content) > 0 else None
        return content

    def iterate_through_pages(self, from_time: int) -> Generator[list, None, None]:
        offset = 0

        while self.running:
            events = self.fetch_page(from_time=from_time, offset=offset)
            if not events:
                return

            yield events
            offset += len(events)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_timestamp_seen = self.from_date
        current_lag: int = 0

        for next_events in self.iterate_through_pages(most_recent_timestamp_seen):
            if next_events:
                # Filter out old, but ongoing detections
                next_events = [event for event in next_events if event["start_time"] >= most_recent_timestamp_seen]
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(next_events))

                if len(next_events) > 0:
                    last_event = max(next_events, key=lambda x: x["start_time"])
                    last_event_timestamp = last_event["start_time"]

                    if last_event_timestamp > most_recent_timestamp_seen:
                        most_recent_timestamp_seen = last_event_timestamp

                    current_lag = int(time.time() - (most_recent_timestamp_seen / 1000.0))

                yield next_events

        if most_recent_timestamp_seen > self.from_date:
            self.from_date = most_recent_timestamp_seen + 1
            self.set_last_timestamp(last_timestamp=self.from_date)

        # Report the current lag
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

    def next_batch(self) -> None:
        batch_start_time = time.time()

        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                self.push_events_to_intakes(events=batch_of_events)
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def run(self) -> None:
        self.log(message="Start fetching ExtraHop Reveal 360 alerts", level="info")

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
