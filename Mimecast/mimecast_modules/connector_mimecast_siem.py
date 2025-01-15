import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from operator import itemgetter
from threading import Event, Lock, Thread
from typing import Generator

import orjson
import requests
from dateutil.parser import isoparse
from pyrate_limiter import Duration, Limiter, RequestRate
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from . import MimecastModule
from .client import ApiClient, ApiKeyAuthentication
from .helpers import download_batches, get_upper_second
from .logging import get_logger
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class MimecastSIEMConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 100
    ratelimit_per_minute: int = 20


class MimecastSIEMWorker(Thread):
    def __init__(self, connector: "MimecastSIEMConnector", log_type: str):
        super().__init__()
        self.connector = connector
        self.log_type: str = log_type

        self.cursor = CheckpointDatetime(
            path=self.connector._data_path,
            start_at=timedelta(days=1),
            ignore_older_than=timedelta(days=7),
            lock=self.connector.context_lock,
            subkey=self.log_type,
        )

        self.from_date = self.cursor.offset
        self._stop_event = Event()

    def log(self, *args, **kwargs):
        self.connector.log(*args, **kwargs)

    def log_exception(self, *args, **kwargs):
        self.connector.log_exception(*args, **kwargs)

    def stop(self):
        self._stop_event.set()

    @property
    def running(self):
        return not self._stop_event.is_set()

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            auth=self.connector.api_auth,
            limiter_batch=self.connector.limiter_batch,
            limiter_default=self.connector.limiter_default,
        )

    @staticmethod
    def __format_datetime(dt: datetime) -> str:
        base = dt.strftime("%Y-%m-%dT%H:%M:%S")
        ms = dt.strftime("%f")[:3]
        return f"{base}.{ms}Z"

    def __fetch_next_events(self, from_date: datetime) -> Generator[list, None, None]:
        url = "https://api.services.mimecast.com/siem/v1/batch/events/cg"
        params: dict[str, int | str] = {
            "pageSize": self.connector.configuration.chunk_size,
            "type": self.log_type,
            "dateRangeStartsAt": from_date.strftime("%Y-%m-%d"),
        }
        response = self.client.get(url, params=params, timeout=60, headers={"Accept": "application/json"})

        while self.running:
            response.raise_for_status()

            result = response.json()

            batch_urls = [item["url"] for item in result.get("value", [])]
            events = download_batches(urls=batch_urls)
            logger.debug("Collected events", nb_url=len(events))

            # The cursor is a date, not a datetime. Thus, we have to download all events from the
            # day's start and then filter out all events with timestamps before `from_date`
            events = [event for event in events if event["timestamp"] > from_date.timestamp() * 1000]
            logger.debug("Filtered events", nb_url=len(events))

            if len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.connector.configuration.intake_key).inc(len(events))
                yield events

            else:
                logger.info("The last page of events was empty", log_type=self.log_type)
                return

            next_page_token = result.get("@nextPage")

            if not next_page_token:
                return

            params["nextPage"] = next_page_token
            response = self.client.get(url, params=params, timeout=60, headers={"Accept": "application/json"})

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date
        current_lag: int = 0

        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    # extract latest timestamp
                    last_event = max(next_events, key=lambda x: x.get("timestamp"))
                    last_event_date = datetime.fromtimestamp(last_event["timestamp"] / 1000).astimezone(timezone.utc)

                    if last_event_date > most_recent_date_seen:
                        most_recent_date_seen = get_upper_second(last_event_date)  # get the upper second

                    yield next_events

        except requests.exceptions.HTTPError as error:
            error_response = error.response
            if error_response is None:
                raise ValueError("Response does not contain any valid data")

            http_error_code = error_response.status_code
            error_message = ", ".join(map(itemgetter("message"), error_response.json().get("fail", [])))
            if http_error_code == 401:
                message = "Authentication failed"

                if error_message is not None and len(error_message) > 0:
                    message = f"{message}: {error_message}"

                self.log(message=message, level="critical")

            if http_error_code == 403:
                message = "Permission denied"

                if error_message is not None and len(error_message) > 0:
                    message = f"{message}: {error_message}"

                self.log(message=message, level="critical")

            raise error

        finally:
            # save the most recent date
            if most_recent_date_seen > self.from_date:
                self.from_date = most_recent_date_seen

                # save in context the most recent date seen
                self.cursor.offset = most_recent_date_seen

                # Update the current lag only if the most_recent_date_seen was updated
                delta_time = datetime.now(timezone.utc) - most_recent_date_seen
                current_lag = int(delta_time.total_seconds())

        EVENTS_LAG.labels(intake_key=self.connector.configuration.intake_key).set(current_lag)

    def next_batch(self) -> None:
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        has_forwarded_events: bool = False
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"{self.log_type}: Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                OUTCOMING_EVENTS.labels(intake_key=self.connector.configuration.intake_key).inc(len(batch_of_events))
                self.connector.push_events_to_intakes(events=batch_of_events)
                has_forwarded_events = True

        # log if no events were collected and forwarded
        if not has_forwarded_events:
            self.log(
                message=f"{self.log_type}: No events to forward",
                level="info",
            )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.info("Fetched and forwarded events", log_type=self.log_type, duration=batch_duration)
        FORWARD_EVENTS_DURATION.labels(intake_key=self.connector.configuration.intake_key).observe(batch_duration)

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.connector.configuration.frequency - batch_duration
        if delta_sleep > 0:
            self.log(message=f"{self.log_type}: Next batch in the future. Waiting {delta_sleep} seconds", level="info")
            time.sleep(delta_sleep)

    def run(self) -> None:
        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message=f"{self.log_type}: Failed to forward events")

                # In case of exception, pause the thread before the next attempt
                time.sleep(self.connector.configuration.frequency)


class MimecastSIEMConnector(Connector):
    module: MimecastModule
    configuration: MimecastSIEMConfiguration

    TYPES_TO_GET = (
        "attachment protect",
        "av",
        "delivery",
        "impersonation protect",
        "internal email protect",
        "journal",
        "process",
        "receipt",
        "spam",
        "url protect",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self._data_path)
        self.context_lock = Lock()

        # 50 times within a 15 minutes fixed window
        batch_rate = RequestRate(limit=50, interval=Duration.MINUTE * 15)
        self.limiter_batch = Limiter(batch_rate)

        default_rate = RequestRate(limit=20, interval=Duration.MINUTE)
        self.limiter_default = Limiter(default_rate)

        self.api_auth = ApiKeyAuthentication(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            limiter=self.limiter_default,
        )

    def start_consumers(self) -> dict[str, MimecastSIEMWorker]:
        consumers = {}
        for consumer_name in self.TYPES_TO_GET:
            consumers[consumer_name] = MimecastSIEMWorker(connector=self, log_type=consumer_name)
            consumers[consumer_name].start()

        return consumers

    def supervise_consumers(self, consumers: dict[str, MimecastSIEMWorker]) -> None:
        for consumer_name, consumer in consumers.items():
            if consumer is None or (not consumer.is_alive() and consumer.running):
                self.log(message=f"Restarting `{consumer_name}` consumer", level="info")  # pragma: no cover

                consumers[consumer_name] = MimecastSIEMWorker(connector=self, log_type=consumer_name)
                consumers[consumer_name].start()

    def stop_consumers(self, consumers: dict[str, MimecastSIEMWorker]):
        for consumer_name, consumer in consumers.items():
            if consumer is not None and consumer.is_alive():
                self.log(message=f"Stopping `{consumer_name}` consumer", level="info")  # pragma: no cover
                consumer.stop()  # pragma: no cover

    def run(self) -> None:
        consumers = self.start_consumers()
        while self.running:
            self.supervise_consumers(consumers)
            time.sleep(5)

        self.stop_consumers(consumers)
