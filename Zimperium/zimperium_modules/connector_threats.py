import os
import time
from datetime import datetime, timedelta, timezone
from functools import cached_property
from posixpath import join as urljoin
from typing import Any, Generator

import orjson
import requests
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.helpers.timestepper import TimeStepper
from sekoia_automation.storage import PersistentJSON

from . import ZimperiumModule
from .client import ApiClient
from .logging import get_logger
from .metrics import (
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
)

logger = get_logger()


class MobileThreatDefenceConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000

    frequency: int = 60
    timedelta: int = 5
    start_time: int = 1


class MobileThreatDefenceConnector(Connector):
    module: ZimperiumModule
    configuration: MobileThreatDefenceConnectorConfiguration

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.context = PersistentJSON("context.json", self.data_path)
        self.cache_size = int(os.getenv("EVENTS_CACHE_SIZE", 2000))
        self.events_cache: Cache[str, bool] = self.load_events_cache()

    @cached_property
    def stepper(self) -> TimeStepper:
        with self.context as cache:
            most_recent_date_requested_str = cache.get("most_recent_date_requested")

        if most_recent_date_requested_str is None:
            return TimeStepper.create(
                trigger=self,
                frequency=self.configuration.frequency,
                timedelta=self.configuration.timedelta,
                start_time=self.configuration.start_time,
                metric=EVENTS_LAG,
            )

        # parse the most recent requested date
        most_recent_date_requested = isoparse(most_recent_date_requested_str)

        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)
        if most_recent_date_requested < one_week_ago:
            most_recent_date_requested = one_week_ago

        return TimeStepper.create_from_time(
            trigger=self,
            start=most_recent_date_requested,
            frequency=self.configuration.frequency,
            timedelta=self.configuration.timedelta,
            metric=EVENTS_LAG,
        )

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

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            base_url=self.module.configuration.base_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    def handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Zimperium MTD API to fetch events failed with status {response.status_code} - {response.reason}"

            # enrich error logs with detail from the Zimperium MTD API
            try:
                error = response.json()
                message = f"{message}: {error['detail']}"

            except Exception:
                pass

            self.log(message, level="error")
            logger.error(
                message,
                response_content=response.text,
            )
            response.raise_for_status()

    def fetch_events(
        self, from_date: datetime, to_date: datetime
    ) -> Generator[list[dict[str, Any]], None, None]:
        page_num = 0

        headers = {"Accept": "application/json"}
        url = urljoin(
            self.module.configuration.base_url, "api/threats/public/v1/threats"
        )
        params: dict[str, str | int] = {
            "module": "ZIPS",
            "after": from_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "before": to_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page": page_num,
            "size": self.configuration.chunk_size,
            "sort": "timestamp,asc",
        }

        while self.running:
            response = self.client.get(url, params=params, headers=headers, timeout=60)
            self.handle_response_error(response)

            raw = response.json()
            events = raw.get("content", [])

            if len(events) > 0:
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(
                    len(events)
                )
                yield events

            else:
                self.log(
                    "Last page was empty. Waiting for the next batch", level="info"
                )
                return

            if raw["last"] is True:
                return

            page_num += 1
            params["page"] = page_num

    def is_processed(self, event: dict[str, Any]) -> bool:
        return event["id"] in self.events_cache

    def mark_processed(self, event: dict[str, Any]) -> None:
        self.events_cache[event["id"]] = True

    def run(self) -> None:  # pragma: no cover
        self.log(message="Zimperium MTD connector has started.", level="info")

        for start, end in self.stepper.ranges():
            # check if the trigger should stop
            if not self.running:
                break

            try:
                duration_start = time.time()
                for events in self.fetch_events(start, end):
                    batch_of_events = [
                        orjson.dumps(event).decode("utf-8")
                        for event in events
                        if not self.is_processed(event)
                    ]

                    if len(batch_of_events) > 0:
                        self.log(
                            message=f"Forwarding {len(batch_of_events)} events",
                            level="info",
                        )
                        self.push_events_to_intakes(events=batch_of_events)

                        OUTCOMING_EVENTS.labels(
                            intake_key=self.configuration.intake_key
                        ).inc(len(batch_of_events))

                        # mark sent events as processed
                        for event in events:
                            self.mark_processed(event)
                        self.save_events_cache()

                    else:
                        self.log(message="No events to forward", level="info")

                FORWARD_EVENTS_DURATION.labels(
                    intake_key=self.configuration.intake_key
                ).observe(time.time() - duration_start)

            except Exception as ex:
                self.log_exception(ex, message="Failed to fetch events.")
                raise ex

            finally:
                # save in context the most recent date seen
                with self.context as cache:
                    cache["most_recent_date_requested"] = end.isoformat()
