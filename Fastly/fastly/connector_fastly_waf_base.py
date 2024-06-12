import datetime
import time
from abc import abstractmethod
from functools import cached_property
from threading import Event, Lock, Thread
from typing import Generator

import orjson
from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from .client import ApiClient
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class FastlyWAFBasicConnectorConfiguration(DefaultConnectorConfiguration):
    email: str = Field(..., description="User's email")
    token: str = Field(..., description="API token")
    corp: str = Field(..., description="Corporation name", pattern=r"^[0-9a-z_.-]+$")
    site: str | None = Field(None, description="Site name", pattern=r"^[0-9a-z_.-]+$")

    frequency: int = 60
    chunk_size: int = 1000


class FastlyWAFConsumer(Thread):
    base_uri = "https://dashboard.signalsciences.net"

    def __init__(self, connector: "FastlyWAFBaseConnector", name: str, url: str):
        super().__init__()

        self.connector = connector

        # Expecting something like "{base_uri}/api/v0/corps/{corp}/sites/{site}/{endpoint}"
        self.url = url
        self.name = name

        self.from_datetime = self.most_recent_date_seen

        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    def log(self, *args, **kwargs) -> None:
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs) -> None:
        self.connector.log_exception(*args, **kwargs)

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(email=self.connector.configuration.email, token=self.connector.configuration.token)

    @property
    def most_recent_date_seen(self) -> datetime.datetime:
        now = datetime.datetime.now(datetime.timezone.utc)

        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            most_recent_date_seen_str = cache.get(self.name, {}).get("most_recent_date_seen")
        self.connector.context_lock.release()

        # if undefined, retrieve events from the last minute
        if most_recent_date_seen_str is None:
            return now - datetime.timedelta(minutes=1)

        # parse the most recent date seen
        most_recent_date_seen = isoparse(most_recent_date_seen_str)

        # We don't retrieve messages older than one month
        one_month_ago = now - datetime.timedelta(days=30)
        if most_recent_date_seen < one_month_ago:
            most_recent_date_seen = one_month_ago

        return most_recent_date_seen

    def save_checkpoint(self, ts: str) -> None:
        self.connector.context_lock.acquire()
        with self.connector.context as cache:
            if self.name not in cache:
                cache[self.name] = {}

            cache[self.name]["most_recent_date_seen"] = ts
        self.connector.context_lock.release()

    def get_next_url(self, from_datetime: datetime.datetime) -> str:
        from_timestamp = int(from_datetime.timestamp())
        return f"{self.url}?sort=asc&limit={self.connector.configuration.chunk_size}&from={from_timestamp}"

    def fetch_next_events(self, from_datetime: datetime.datetime) -> Generator[list, None, None]:
        next_url = self.get_next_url(from_datetime=from_datetime)
        while self.running:
            response = self.client.get(url=next_url, timeout=60)
            response_content = response.json()

            events = response_content["data"]
            if events:
                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key).inc(len(events))
                yield events

            else:
                self.log(
                    message=f"{self.name}: The last page of events was empty. "
                    f"Waiting {self.connector.configuration.frequency} seconds before fetching next page",
                    level="info",
                )
                time.sleep(self.connector.configuration.frequency)

            next_path = response_content.get("next", {}).get("uri")
            if not next_path:
                return

            next_url = "%s%s" % (self.base_uri, next_path)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_datetime
        try:
            for next_events in self.fetch_next_events(most_recent_date_seen):
                if next_events:
                    last_event_datetime = self.connector.get_datetime_from_item(next_events[-1])
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
                self.save_checkpoint(self.from_datetime.isoformat())

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()
        current_lag: int = 0

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"{self.name}: Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key).inc(len(batch_of_events))
                self.connector.push_events_to_intakes(events=batch_of_events)

                # Compute the current lag from the date of the most recent event seen
                current_lag = int((datetime.datetime.now(datetime.timezone.utc) - self.from_datetime).total_seconds())
            else:
                self.log(
                    message=f"{self.name}: No events to forward",
                    level="info",
                )

        # Monitor the lag
        EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(current_lag)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"{self.name}: Fetched and forwarded events in {batch_duration} seconds",
            level="debug",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(
                message=f"{self.name}: Next batch in the future. Waiting {delta_sleep} seconds",
                level="debug",
            )
            time.sleep(delta_sleep)

    def run(self) -> None:
        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message=f"{self.name}: Failed to forward events")


class FastlyWAFBaseConnector(Connector):
    configuration: FastlyWAFBasicConnectorConfiguration
    base_uri = "https://dashboard.signalsciences.net"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(email=self.configuration.email, token=self.configuration.token)

    def get_sites(self):
        result = []

        page_num = 1
        page_limit = 100
        while True:
            response = self.client.get(
                f"{self.base_uri}/api/v0/corps/{self.configuration.corp}/sites?" f"page={page_num}&limit={page_limit}",
                timeout=60,
            )
            response.raise_for_status()

            site_names = [site["name"] for site in response.json().get("data", [])]
            result.extend(site_names)

            if len(site_names) < page_limit:
                break

            page_num += 1

        return result

    def start_consumers(self):
        consumers = {}

        # Always add endpoint for the corp, if available
        corp_url = self.get_url_for_corp()
        if corp_url:
            consumers[f"corp:{self.configuration.corp}"] = FastlyWAFConsumer(
                connector=self, name=f"corp:{self.configuration.corp}", url=corp_url
            )

        # If site is provided - use it
        # If not - get all sites in the corp
        if self.configuration.site is not None:
            sites = [self.configuration.site]

        else:
            sites = self.get_sites()

        for site in sites:
            consumers[f"site:{site}"] = FastlyWAFConsumer(
                connector=self, name=f"site:{site}", url=self.get_url_for_site(site)
            )

        for consumer_name, consumer in consumers.items():
            self.log(message=f"Starting {consumer_name} consumer", level="info")  # pragma: no cover
            consumer.start()

        return consumers

    @abstractmethod
    def get_url_for_site(self, site_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_url_for_corp(self) -> str | None:
        return None

    @abstractmethod
    def get_datetime_from_item(self, item: dict) -> datetime.datetime:
        return isoparse(item["timestamp"])

    def get_url_by_consumer_name(self, name: str) -> str | None:
        level, label = name.split(":")
        if level == "site":
            return self.get_url_for_site(site_name=name)

        elif level == "corp":
            return self.get_url_for_corp()

        return None

    def supervise_consumers(self, consumers):
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting {consumer_name} consumer", level="info")  # pragma: no cover

                consumers[consumer_name] = FastlyWAFConsumer(
                    connector=self, name=consumer_name, url=self.get_url_by_consumer_name(consumer_name)
                )
                consumers[consumer_name].start()

    def stop_consumers(self, consumers):
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping {consumer_name} consumer", level="info")  # pragma: no cover
                consumer.stop()  # pragma: no cover

    def run(self) -> None:
        consumers = self.start_consumers()
        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
