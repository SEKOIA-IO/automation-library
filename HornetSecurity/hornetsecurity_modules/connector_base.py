from abc import abstractmethod
from collections.abc import Generator
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any
import time

import orjson
from cachetools import Cache
from pydantic.v1 import Field
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from hornetsecurity_modules import HornetsecurityModule
from hornetsecurity_modules.client import ApiClient
from hornetsecurity_modules.helpers import (
    load_events_cache,
    save_events_cache,
    remove_duplicates,
    normalize_uri,
)
from hornetsecurity_modules.logging import get_logger
from hornetsecurity_modules.metrics import (
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
    FORWARD_EVENTS_DURATION,
)
from hornetsecurity_modules.timestepper import TimeStepper


logger = get_logger()


class BaseConnectorConfiguration(DefaultConnectorConfiguration):
    """
    Base configuration for Hornetsecurity connectors.
    """

    frequency: int = Field(300, description="Batch frequency in seconds (default: 300 seconds)")
    chunk_size: int = Field(
        2000,
        description="Max size of chunks for batch processing (default: 2000 items)",
    )
    timedelta: int = Field(0, description="Time delta in minutes to fetch events (default: 0 minutes)")
    ratelimit_per_second: int = Field(
        20,
        description="Rate limit per second for API requests (default: 20 requests per second)",
    )


class BaseConnector(Connector):
    module: HornetsecurityModule
    configuration: BaseConnectorConfiguration
    ID_FIELD: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cursor = CheckpointDatetime(
            path=self._data_path,
            start_at=timedelta(hours=24),
            ignore_older_than=timedelta(days=7),
        )
        self.events_cache: Cache = load_events_cache(self.cursor._context, maxsize=1000)

    @cached_property
    def time_stepper(self) -> TimeStepper:
        """
        Create a TimeStepper instance for managing time ranges.

        Returns:
            TimeStepper: The TimeStepper instance.
        """
        return TimeStepper.create_from_time(
            trigger=self,
            start=self.cursor.offset,
            frequency=self.configuration.frequency,
            timedelta=self.configuration.timedelta,
        )

    @cached_property
    def client(self) -> ApiClient:
        """
        Get the API client for the current connector.

        Returns:
            ApiClient: The API client instance.
        """
        return ApiClient(
            api_token=self.module.configuration.api_token,
            ratelimit_per_second=self.configuration.ratelimit_per_second,
        )

    @cached_property
    def url(self):
        """
        Construct the base URL for the API.
        """
        return normalize_uri(self.module.configuration.hostname)

    @abstractmethod
    def _fetch_events(self, from_date: datetime, to_date: datetime) -> Generator[list[dict[str, Any]], None, None]:
        """
        Fetch events from the current context.

        Args:
            from_date: datetime - The start date for fetching events.
            to_date: datetime - The end date for fetching events.

        Yields:
            list[dict[str, Any]]: The fetched events
        """
        raise NotImplementedError("This method should be implemented in a subclass")

    def fetch_events(self) -> Generator[list, None, None]:
        for start_date, end_date in self.time_stepper.ranges():
            for fetched_events in self._fetch_events(start_date, end_date):
                # fetch events from the current context
                INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(fetched_events))

                if next_events := remove_duplicates(fetched_events, self.events_cache, self.ID_FIELD):
                    # forward current events
                    yield next_events

            # save in context the end date of the last batch period
            self.cursor.offset = end_date

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        batch_of_events = []
        for events in self.fetch_events():
            # for each fetched event
            for event in events:
                # add to the batch as json-serialized object
                batch_of_events.append(orjson.dumps(event).decode("utf-8"))

                # if the batch is full, push it
                if len(batch_of_events) >= self.configuration.chunk_size:
                    self.log(
                        message=f"Forward {len(batch_of_events)} events to the intake",
                        level="info",
                    )
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
                    self.push_events_to_intakes(events=batch_of_events)
                    batch_of_events = []

        # if the last batch is not empty, push it
        if len(batch_of_events) > 0:
            self.log(
                message=f"Forward {len(batch_of_events)} events to the intake",
                level="info",
            )
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(batch_of_events))
            self.push_events_to_intakes(events=batch_of_events)

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        self.log(
            message=f"Fetch and forward {len(batch_of_events)} events in {batch_duration} seconds",
            level="info",
        )
        FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

    def run(self):  # pragma: no cover
        # Start the connector and run the event fetching loop.
        self.log(
            message="Starting connector",
            level="info",
        )

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                logger.error(
                    "Error while fetching and forwarding events",
                    error=error,
                    exc_info=True,
                )
                self.log_exception(error, message="Failed to forward events")

        self.log(
            message="Stopping connector",
            level="info",
        )

        # Save the events cache to the context
        save_events_cache(
            self.events_cache,
            self.cursor._context,
        )
