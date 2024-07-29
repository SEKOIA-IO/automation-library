import os
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any
from posixpath import join as urljoin

import orjson
import requests
from dateutil.parser import isoparse
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.metrics import PrometheusExporterThread, make_exporter
from sekoia_automation.storage import PersistentJSON

from jumpcloud_modules import JumpcloudDirectoryInsightsModule
from jumpcloud_modules.client import ApiClient
from jumpcloud_modules.helpers import get_upper_second
from jumpcloud_modules.logging import get_logger
from jumpcloud_modules.metrics import (
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
)

logger = get_logger()


class FetchEventsException(Exception):
    pass


class JumpcloudDirectoryInsightsConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    service: str = Field(
        "all",
        description="Name of the Jumpcloud service for which you want to collect logs",
    )


class JumpcloudDirectoryInsightsConnector(Connector):
    """
    This connector fetches system logs from Jumpcloud Directory Insights API
    """

    module: JumpcloudDirectoryInsightsModule
    configuration: JumpcloudDirectoryInsightsConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.most_recent_date_seen
        self.fetch_events_limit = 1000

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Jumpcloud Directory Insights logs connector", level="info")
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @property
    def most_recent_date_seen(self):
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
    def client(self):
        return ApiClient(self.module.configuration.apikey)

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = f"Request to Jumpcloud Directory Insights API to fetch events \
failed with status {response.status_code} - {response.reason}"

            # enrich error logs with detail from the Jumpcloud Directory Insights API
            try:
                error = response.json()
                message = f"{message}: {error['message']}"
            except Exception:
                pass

            raise FetchEventsException(message)

    def __fetch_next_events(self, from_date: datetime) -> Generator[list, None, None]:
        # set parameters
        params: dict[str, Any] = {
            "start_time": from_date.isoformat(),
            "limit": self.fetch_events_limit,
            "sortOrder": "ASC",
            "service": [self.configuration.service],
        }

        # get the first page of events
        headers = {"Accept": "application/json", "Content-type": "application/json"}
        url = urljoin(self.module.configuration.base_url, "insights/directory/v1/events")
        response = self.client.post(url, json=params, headers=headers)

        while self.running:
            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            events = response.json()
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(events or []))

            # yielding events if defined
            if events:
                yield events
            else:
                logger.info(
                    "The last page of events was empty. "
                    "Waiting {self.configuration.frequency}s "
                    "before fetching next batch"
                )
                time.sleep(self.configuration.frequency)

            # checking if there are more pages to retrieve
            if (response.headers["X-Result-Count"] == response.headers["X-Limit"]) and (
                response.headers["X-Search_after"] is not None
            ):
                params["search_after"] = orjson.loads(response.headers["X-Search_after"])
                response = self.client.post(url, json=params, headers=headers)
            else:
                return

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if next_events:
                # get the greater date seen in this list of events
                events_date = list(
                    sorted(
                        filter(
                            lambda x: x is not None,
                            map(lambda x: x["timestamp"], next_events),
                        )
                    )
                )
                last_event_date = isoparse(events_date[-1])

                # save the greater date ever seen
                if last_event_date > most_recent_date_seen:
                    most_recent_date_seen = get_upper_second(
                        last_event_date
                    )  # get the upper second to exclude the most recent event seen

                # forward current events
                yield next_events

        # save the most recent date
        current_lag: int = 0
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen

            # save in context the most recent date seen
            with self.context as cache:
                cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

            delta_time = datetime.now(timezone.utc) - self.from_date
            current_lag = int(delta_time.total_seconds())
            self.log(
                message=f"Current lag {current_lag} seconds.",
                level="info",
            )

        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

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
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
                self.push_events_to_intakes(events=batch_of_events)
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
            logger.debug("Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching Jumpcloud Directory Insights logs", level="info")

        # start the prometheus exporter
        exporter = make_exporter(
            PrometheusExporterThread,
            int(os.environ.get("WORKER_PROM_LISTEN_PORT", "8010"), 10),
        )
        exporter.start()

        try:
            while self.running:
                try:
                    self.next_batch()
                except Exception as error:
                    self.log_exception(error, message="Failed to forward events")
        finally:
            # Stop the connector executor
            self._executor.shutdown(wait=True)

            # Stop the exporter
            exporter.stop()
