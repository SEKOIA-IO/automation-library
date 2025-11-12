import signal
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from posixpath import join as urljoin
from threading import Event
from typing import Any, Optional

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from okta_modules import OktaModule
from okta_modules.client import ApiClient
from okta_modules.helpers import get_upper_second
from okta_modules.logging import get_logger
from okta_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

logger = get_logger()


class FetchEventsException(Exception):
    pass


class SystemLogConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    ratelimit_per_minute: int = 20
    filter: str | None = None
    q: str | None = None


class SystemLogConnector(Connector):
    """
    This connector fetches system logs from Okta API
    """

    module: OktaModule
    configuration: SystemLogConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.most_recent_date_seen
        self.fetch_events_limit = 1000

        # Put cache size to 2000 in order to
        self.cache_size = 2000
        self.events_cache: Cache[str, bool] = self.load_events_cache()

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def load_events_cache(self) -> Cache[str, bool]:
        """
        Load the events cache.
        """
        cache: Cache[str, bool] = LRUCache(maxsize=self.cache_size)

        with self.context as context:
            # load the cache from the context
            events_cache = context.get("events_cache", [])

        for uuid in events_cache:
            cache[uuid] = True

        return cache

    def save_events_cache(self) -> None:
        """
        Save the events cache.
        """
        with self.context as context:
            # save the events cache to the context
            context["events_cache"] = list(self.events_cache.keys())

    def exit(self, _: Any, __: Optional[Any]) -> None:
        self.log(message="Stopping OKTA system logs connector", level="info")
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @property
    def most_recent_date_seen(self) -> datetime:
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last minute
            if most_recent_date_seen_str is None:
                return now - timedelta(minutes=1)

            # parse the most recent date seen
            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            # We don't retrieve messages older than one week
            one_week_ago = now - timedelta(days=7)
            if most_recent_date_seen < one_week_ago:
                most_recent_date_seen = one_week_ago

            return most_recent_date_seen

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            apikey=self.module.configuration.apikey.get_secret_value(),
            ratelimit_per_minute=self.configuration.ratelimit_per_minute,
        )

    def _handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = (
                f"Request on Okta API to fetch events failed with status {response.status_code} - {response.reason}"
            )

            # enrich error logs with detail from the Okta API
            try:
                error = response.json()
                message = f"{message}: {error['errorCode']} - {error['errorSummary']}"
            except Exception:
                pass

            raise FetchEventsException(message)

    def __fetch_next_events(self, from_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        # set parameters
        params: dict[str, str | int] = {
            "since": from_date.isoformat(),
            "limit": self.fetch_events_limit,
            "sortOrder": "ASCENDING",
        }

        # add optional parameters
        for param_name in ("filter", "q"):
            value = getattr(self.configuration, param_name)

            if value is not None:
                params[param_name] = value

        # get the first page of events
        headers = {"Accept": "application/json"}
        url = urljoin(self.module.configuration.base_url, "api/v1/logs")
        response = self.client.get(url, params=params, headers=headers)

        while not self._stop_event.is_set():
            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            events = response.json()

            filtered_events = [
                event for event in events if event.get("uuid") is not None and event["uuid"] not in self.events_cache
            ]

            # yielding events if defined
            if filtered_events:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(filtered_events))
                yield filtered_events
            else:
                logger.info(
                    f"The last page of events was empty. Waiting {self.configuration.frequency}s "
                    "before fetching next page"
                )
                time.sleep(self.configuration.frequency)

            url = response.links.get("next", {}).get("url")
            if url is None:
                return

            response = self.client.get(url, headers=headers)

    def fetch_events(self) -> Generator[list[dict[str, Any]], None, None]:
        most_recent_date_seen = self.from_date

        try:
            for next_events in self.__fetch_next_events(most_recent_date_seen):
                if next_events:
                    # get the greater date seen in this list of events
                    events_date: list[str] = sorted(
                        x["published"] for x in next_events if x.get("published") is not None
                    )

                    last_event_date = isoparse(events_date[-1])

                    # save the greater date ever seen
                    if last_event_date > most_recent_date_seen:
                        most_recent_date_seen = get_upper_second(
                            last_event_date
                        )  # get the upper second to exclude the most recent event seen

                    # forward current events
                    yield next_events
        finally:
            # save the most recent date
            if most_recent_date_seen > self.from_date:
                self.from_date = most_recent_date_seen

                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

        now = datetime.now(timezone.utc)
        current_lag = now - most_recent_date_seen
        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(int(current_lag.total_seconds()))

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
                )
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                self.push_events_to_intakes(events=batch_of_events)

                # Persist cache of event UUIDs after pushing to intake
                for event in events:
                    self.events_cache[event["uuid"]] = True

                self.save_events_cache()
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

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
        self.log(message="Start fetching OKTA system logs", level="info")

        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
