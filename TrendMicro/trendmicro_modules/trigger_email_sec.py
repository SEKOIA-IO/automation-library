import time
import traceback
import urllib.parse
from collections.abc import Generator
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Any

import orjson
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import TrendMicroModule
from .client import ApiClient
from .helpers import iso8601_to_timestamp, unixtime_to_iso8601
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class LogsPageRequestError(Exception):
    pass


class TrendMicroConnectorConfiguration(DefaultConnectorConfiguration):
    service_url: str = Field(..., description="Service URL")
    username: str = Field(..., description="Username")
    api_key: str = Field(..., description="API key", json_schema_extra={"secret": True})
    frequency: int = 60
    batch_size: int = 500


class TrendMicroWorker(Thread):
    API_VERSION = "v1"

    def __init__(self, connector: TrendMicroEmailSecurityConnector, log_type: str):
        super().__init__()

        self.log_type = log_type
        self.connector = connector

        self.service_url = connector.configuration.service_url.rstrip("/")
        if self.service_url.startswith("http://"):
            self.service_url = f"https://{self.service_url[7:]}"

        elif not self.service_url.startswith("https://"):
            self.service_url = f"https://{self.service_url}"

        self._stop_event = Event()
        self.all_pages_fetched = False

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @property
    def frequency(self):
        return self.connector.configuration.frequency

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(username=self.connector.configuration.username, api_key=self.connector.configuration.api_key)

    def get_last_timestamp(self) -> int:
        now = int(time.time())  # in seconds

        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_ts_seen = cache.get(self.log_type, {}).get("last_timestamp")
        self.connector.context_lock.release()

        # if undefined, retrieve events from the last 5 minutes.
        # This lower bound is persisted: if the first window is interrupted, the next run must restart from it
        # instead of computing a later one, otherwise the events of the unread pages would be skipped.
        if most_recent_ts_seen is None:
            most_recent_ts_seen = now - 5 * 60
            self.set_last_timestamp(most_recent_ts_seen)
            return most_recent_ts_seen

        # We can't retrieve messages older than 72 hours
        one_week_ago = now - 72 * 60 * 60
        if most_recent_ts_seen < one_week_ago:
            most_recent_ts_seen = one_week_ago

        return most_recent_ts_seen

    def get_recent_pushed_events(self) -> list[Any]:
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            result = cache.get(self.log_type, {}).get("recent_pushed_events", [])
        self.connector.context_lock.release()

        return result

    def set_last_timestamp(self, last_timestamp: int) -> None:
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            if self.log_type not in cache.keys():
                cache[self.log_type] = {}

            cache[self.log_type]["last_timestamp"] = last_timestamp

        self.connector.context_lock.release()

    # Several logs can share the same mail and action (e.g. one per recipient, or successive deferrals):
    # the recipient and the generation time are part of the identity of a log
    EVENT_KEY_FIELDS = ("mailID", "messageID", "action", "recipient", "genTime")

    @classmethod
    def get_event_metadata(cls, event: dict[str, Any]) -> dict[str, Any]:
        return {field: event.get(field) for field in cls.EVENT_KEY_FIELDS}

    @classmethod
    def get_event_key(cls, metadata: dict[str, Any]) -> tuple:
        return tuple(
            tuple(value) if isinstance(value, list) else value for value in map(metadata.get, cls.EVENT_KEY_FIELDS)
        )

    def set_recent_pushed_events(self, events: list[Any]) -> None:
        self.connector.context_lock.acquire()

        with self.connector.context as cache:
            if self.log_type not in cache.keys():
                cache[self.log_type] = {}

            cache[self.log_type]["recent_pushed_events"] = [self.get_event_metadata(event) for event in events]

        self.connector.context_lock.release()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def request_logs_page(self, params: dict) -> dict | None:
        url = f"{self.service_url}/api/{self.API_VERSION}/log/mailtrackinglog"
        response = self.client.get(url, params=params, timeout=60)

        if not response.ok:
            self.log(
                message=(
                    f"Request on Trend Micro Email Security API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response.reason}: {response.text}"
                ),
                level="error",
            )

            raise LogsPageRequestError(f"Failed to fetch {response.url} (status {response.status_code})")

        else:
            content = response.json() if len(response.content) > 0 else None
            return content

    def iterate_through_pages(self, from_timestamp: int) -> Generator[list]:
        timestamp_now = int(time.time())
        params = {
            "type": self.log_type,
            "start": unixtime_to_iso8601(from_timestamp),
            "end": unixtime_to_iso8601(timestamp_now),
            "limit": self.connector.configuration.batch_size,
        }
        self.all_pages_fetched = False

        while self.running:
            try:
                content = self.request_logs_page(params=params)

            except LogsPageRequestError:
                if "token" in params:
                    # a page behind a nextToken could not be fetched: the window is incomplete
                    self.log(
                        message=f"{self.log_type}: Failed to fetch the next page of events. The window will be retried",  # noqa: E501
                        level="warning",
                    )
                    return

                content = None

            if content is None:
                self.all_pages_fetched = True

                # an empty page behind a nextToken just means that there are no more events
                if "token" in params:
                    return

                self.log(
                    message=f"{self.log_type}: No events to forward. Waiting {self.frequency} seconds",
                    level="info",
                )
                time.sleep(self.frequency)
                return

            events = content.get("logs")
            next_token = content.get("nextToken")

            # an empty page can still be followed by other pages: only the absence of nextToken ends the window
            if events:
                yield events

            if next_token is not None:
                params["token"] = urllib.parse.unquote(next_token)  # it's provided url-encoded by API

            else:
                self.all_pages_fetched = True
                return

    def fetch_events(self, from_timestamp: int) -> Generator[list]:
        for events in self.iterate_through_pages(from_timestamp):
            if events:
                yield events

    def next_batch(self):
        batch_start_time = time.time()

        previous_timestamp = self.get_last_timestamp()
        # Events cached by previous versions lack recipient and genTime: they never match, so the few events of
        # the boundary second are pushed again once after an upgrade, rather than dropping distinct logs that share
        # the same mail and action
        recent_pushed_events = {self.get_event_key(metadata) for metadata in self.get_recent_pushed_events()}

        # keep only the genTime and the metadata of the pushed events, not their payloads,
        # to bound the memory used by a large catch-up window
        pushed_events: list[tuple[int, dict[str, Any]]] = []
        has_fetched_events = False

        # Iterate through all the pages of the window and push each page as soon as it is fetched
        for events in self.fetch_events(previous_timestamp):
            has_fetched_events = True

            # skip the events already pushed in the previous run (boundary second) or earlier in this run
            next_events = []
            for event in events:
                event_key = self.get_event_key(event)
                if event_key not in recent_pushed_events:
                    recent_pushed_events.add(event_key)
                    next_events.append(event)

            if len(next_events) > 0:
                batch_of_events = [orjson.dumps(event).decode("utf-8") for event in next_events]
                self.log(
                    message=f"{self.log_type}: Forwarded {len(next_events)} events to the intake",
                    level="info",
                )
                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).inc(
                    len(next_events)
                )

                self.connector.push_events_to_intakes(events=batch_of_events)
                pushed_events.extend(
                    (iso8601_to_timestamp(event.get("genTime")), self.get_event_metadata(event))
                    for event in next_events
                )

                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).inc(
                    len(batch_of_events)
                )

            if not self.running:
                break

        # The API doesn't guarantee that logs are sorted by genTime, so the maximum genTime of a page can be newer
        # than events of the pages not fetched yet. The checkpoint is therefore persisted only once all the pages
        # of the window have been pushed: an interruption between pages leads to the window being collected again
        # (duplicates are possible) instead of skipping unpushed events.
        if len(pushed_events) > 0 and self.all_pages_fetched:
            last_event_timestamp = max(gen_time for gen_time, _ in pushed_events)
            new_timestamp = max(last_event_timestamp, previous_timestamp)

            # The next run queries from the checkpoint second, inclusive: only the events of this second
            # have to be remembered to avoid duplicates, which keeps the cache bounded.
            boundary_events = [metadata for gen_time, metadata in pushed_events if gen_time == new_timestamp]
            if new_timestamp > previous_timestamp:
                self.set_last_timestamp(new_timestamp)
                self.set_recent_pushed_events(boundary_events)

            elif len(boundary_events) > 0:
                # the checkpoint doesn't move: keep the previous events of this second as well
                self.set_recent_pushed_events(self.get_recent_pushed_events() + boundary_events)

            events_lag = int(time.time()) - new_timestamp
            EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).set(events_lag)

        elif has_fetched_events and len(pushed_events) == 0:
            self.log(
                message=f"{self.log_type}: No events to forward. Waiting {self.frequency} seconds",
                level="info",
            )
            time.sleep(self.frequency)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)

        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key, type=self.log_type).observe(
            batch_duration
        )

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.log_type}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="info",
            )
            time.sleep(delta_sleep)

    def run(self):  # pragma: no cover
        self.log(
            message=f"Start fetching `{self.log_type}` logs from Trend Micro Email Security",
            level="info",
        )

        while self.running:
            try:
                self.next_batch()

            except Exception as error:
                traceback.print_exc()
                self.log_exception(error, message="Failed to forward events")


class TrendMicroEmailSecurityConnector(Connector):
    configuration: TrendMicroConnectorConfiguration
    module: TrendMicroModule

    WORKER_TYPES = ("accepted_traffic", "blocked_traffic")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

        self.consumers = {}

    def start_consumers(self) -> dict[str, TrendMicroWorker]:
        consumers = {}

        for consumer_name in self.WORKER_TYPES:
            self.log(message=f"Start `{consumer_name}` consumer", level="info")
            consumers[consumer_name] = TrendMicroWorker(connector=self, log_type=consumer_name)
            consumers[consumer_name].start()

        return consumers

    def supervise_consumers(self, consumers: dict[str, TrendMicroWorker]):
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting `{consumer_name}` consumer", level="info")

                consumers[consumer_name] = TrendMicroWorker(connector=self, log_type=consumer_name)
                consumers[consumer_name].start()

    def stop_consumers(self, consumers: dict[str, TrendMicroWorker]):
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping `{consumer_name}` consumer", level="info")
                consumer.stop()

    def run(self):  # pragma: no cover
        consumers = self.start_consumers()

        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
