import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from loguru import logger
from pydantic import BaseModel, HttpUrl
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from wiz.client.gql_client import GetAlertsResult, WizErrors, WizGqlClient
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

    _wiz_gql_client: WizGqlClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init SalesforceConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def last_event_date(self) -> datetime:  # pragma: no cover
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 1 hour
            if last_event_date_str is None:
                return one_hour_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

            # We don't retrieve messages older than 1 hour
            if last_event_date < one_hour_ago:
                return one_hour_ago

            return last_event_date

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
        _previous_last_event_date = self.last_event_date

        has_next_page = True
        end_cursor: str | None = None

        total_events = 0

        while has_next_page:
            result = await self.get_events(start_date=_previous_last_event_date, cursor=end_cursor)

            # Push the collected events
            pushed_events = await self.push_data_to_intakes(
                [orjson.dumps(event).decode("utf-8") for event in result.data]
            )

            with self.context as cache:
                cache["last_event_date"] = result.new_last_event_date.isoformat()

            total_events += len(pushed_events)

            has_next_page = result.has_next_page
            end_cursor = result.end_cursor

        return total_events

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()
                result = await self.single_run()
                last_event_date = self.last_event_date
                processing_end = time.time()

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key, type=self.product_name).set(
                    processing_end - last_event_date.timestamp()
                )

                log_message = "No records to forward"
                if result > 0:
                    log_message = "Pushed {0} records".format(result)

                self.log(message=log_message, level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(result)

                processing_time = processing_end - processing_start
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(processing_time)
                logger.info(
                    "Processing took {processing_time} seconds",
                    processing_time=processing_time,
                )

                if result == 0:
                    await asyncio.sleep(self.configuration.frequency)

            except WizErrors as error:
                # In case if we handle the server custom error we should raise critical message and then sleep.
                # This will help to stop the connector in case if credentials are invalid or permissions denied.
                self.log(message=error.message, level="critical")
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

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())
