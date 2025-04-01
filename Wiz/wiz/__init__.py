import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Sequence

import orjson
from cachetools import Cache, LRUCache
from loguru import logger
from pydantic.v1 import BaseModel, HttpUrl
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module

from wiz.client.gql_client import WizErrors, WizGqlClient, WizResult, WizServerError
from wiz.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class WizModuleConfig(BaseModel):
    """Configuration for WizModule."""

    tenant_url: HttpUrl
    client_id: str
    client_secret: str


class WizModule(Module):
    """WizModule."""

    configuration: WizModuleConfig


class Result(BaseModel):
    has_next_page: bool
    end_cursor: str | None
    new_last_event_date: datetime
    data: list[dict[str, Any]]


class WizConnectorConfig(DefaultConnectorConfiguration):
    """WizConnector configuration."""

    frequency: int = 60


class WizConnector(AsyncConnector, ABC):
    """WizConnector."""

    configuration: WizConnectorConfig

    module: WizModule

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init WizConnector."""

        super().__init__(*args, **kwargs)
        self._wiz_gql_client: WizGqlClient | None = None
        self.events_cache: Cache = LRUCache(maxsize=10000)
        self.last_event_date = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=7),
        )

    @property
    def wiz_gql_client(self) -> WizGqlClient:  # pragma: no cover
        """
        Get wiz client.

        Returns:
            WizGqlClient:
        """
        if self._wiz_gql_client is not None:
            return self._wiz_gql_client

        self._wiz_gql_client = WizGqlClient.create(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            tenant_url=self.module.configuration.tenant_url,
        )

        return self._wiz_gql_client

    @abstractmethod
    async def get_events(self, start_date: datetime, cursor: str | None = None) -> Result:
        raise NotImplementedError("Method get_events must be implemented")

    async def single_run(self) -> int:
        """
        Process events with single run.

        Returns:
            int: total number of events processed
        """
        _previous_last_event_date = self.last_event_date.offset

        has_next_page = True
        end_cursor: str | None = None

        total_events = 0

        while has_next_page:
            result = await self.get_events(start_date=_previous_last_event_date, cursor=end_cursor)

            # Push the collected events
            pushed_events = await self.push_data_to_intakes(
                [
                    orjson.dumps(event).decode("utf-8")
                    for event in filter_collected_events(result.data, lambda event: event["id"], self.events_cache)
                ]
            )

            self.last_event_date.offset = result.new_last_event_date

            total_events += len(pushed_events)

            has_next_page = result.has_next_page
            end_cursor = result.end_cursor

        return total_events

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()
                result = await self.single_run()
                last_event_date = self.last_event_date.offset
                processing_end = time.time()

                events_lag: float = 0
                log_message = "No records to forward"
                if result > 0:
                    log_message = "Pushed {0} records".format(result)
                    events_lag = processing_end - last_event_date.timestamp()

                self.log(message=log_message, level="info")

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(events_lag)

                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(result)

                processing_time = processing_end - processing_start
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(processing_time)
                logger.info(
                    "Processing took {processing_time} seconds",
                    processing_time=processing_time,
                )

                if result == 0:
                    await asyncio.sleep(self.configuration.frequency)

            except WizServerError as error:
                # In case if we handle the server custom error we should raise critical message and then sleep.
                # This will help to stop the connector in case if credentials are invalid or permissions denied.
                self.log(message=error.message, level="critical")
                await asyncio.sleep(self.configuration.frequency)

            except WizErrors as error:
                self.log(message=error.message, level="error")
                await asyncio.sleep(self.configuration.frequency)

            except TimeoutError:
                self.log(message="A timeout was raised by the client", level="warning")
                await asyncio.sleep(self.configuration.frequency)

            except Exception as error:
                self.log_exception(error)
                await asyncio.sleep(self.configuration.frequency)

        await self.wiz_gql_client.close()
        if self._session:
            await self._session.close()

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:  # pragma: no cover
        """
        Stop the connector
        """
        super(Connector, self).stop(*args, **kwargs)

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())


def filter_collected_events(events: Sequence[Any], getter: Callable, cache: Cache) -> list[Any]:
    """
    Filter events that have already been filter_collected_events

    Args:
        events: The list of events to filter
        getter: The callable to get the criteria to filter the events
        cache: The cache that hold the list of collected events
    """

    selected_events = []
    for event in events:
        key = getter(event)

        # If the event was already collected, discard it
        if key is None or key in cache:
            continue

        cache[key] = True
        selected_events.append(event)

    return selected_events
