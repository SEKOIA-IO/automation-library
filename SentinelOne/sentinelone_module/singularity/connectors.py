import asyncio
import time
from abc import ABC
from datetime import timedelta
from functools import cached_property
from typing import Any, Optional

import orjson
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.checkpoint import CheckpointCursor, CheckpointDatetime
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.helpers import filter_collected_events
from sentinelone_module.logs.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from sentinelone_module.singularity.client import SentinelOneServerError, SingularityClient


class SingularityConnectorConfig(DefaultConnectorConfiguration):
    """Configuration for SingularityConnector."""

    frequency: int = 60


class AbstractSingularityConnector(AsyncConnector, ABC):
    module: SentinelOneModule
    configuration: SingularityConnectorConfig

    product_name: str

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.last_event_date = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=7),
        )
        self.events_cache: Cache = LRUCache(maxsize=10000)

    @cached_property
    def client(self) -> SingularityClient:
        return SingularityClient(
            hostname=self.module.configuration.hostname,
            api_token=self.module.configuration.api_token,
        )

    def stop(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """
        Stop the connector.

        Temporary redefine the method to avoid known SDK issues.
        """
        super(Connector, self).stop(*args, **kwargs)

    async def single_run(self) -> int:
        result = 0

        # Set up parameters
        last_event_date = self.last_event_date.offset
        start_time = int(last_event_date.timestamp() * 1000)  # convert the event date into a timestamp in millisecond
        cursor: str | None = None
        has_more_items: bool = True

        # Iter over the responses
        while self.running and has_more_items:
            # Get the next alerts
            data = await self.client.list_alerts(
                product_name=self.product_name,
                start_time=start_time if cursor is None else None,
                after=cursor,
            )

            alerts = filter_collected_events(data.alerts, lambda alert: alert["id"], self.events_cache)

            detailed_alerts = []
            for alert in alerts:
                alert_details = await self.client.get_alert_details(alert["id"]) or {}
                detailed_alerts.append({**alert, **alert_details})

            # Push the collected alerts
            pushed_events = await self.push_data_to_intakes(
                [orjson.dumps(alert).decode("utf-8") for alert in detailed_alerts]
            )

            result += len(pushed_events)

            # Save the most recent date seen
            for alert in data.alerts:
                alert_detected_at = isoparse(alert["detectedAt"])
                if alert_detected_at > last_event_date:
                    last_event_date = alert_detected_at

            # Update parameters for the next page (if exists)
            cursor = data.end_cursor
            has_more_items = data.has_next_page

        self.last_event_date.offset = last_event_date

        return result

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()
                result = await self.single_run()
                last_event_date = self.last_event_date.offset
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

            except SentinelOneServerError as error:
                # In case if we handle the server custom error we should raise critical message and then sleep.
                # This will help to stop the connector in case if credentials are invalid or permissions denied.
                self.log(message=error.message, level="critical")
                await asyncio.sleep(self.configuration.frequency)

            except TimeoutError as error:
                self.log(message="A timeout was raised by the client", level="warning")
                await asyncio.sleep(self.configuration.frequency)

            except Exception as error:
                self.log_exception(error)
                await asyncio.sleep(self.configuration.frequency)

        await self.client.close()
        if self._session:
            await self._session.close()

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())


class SingularityIdentityConnector(AbstractSingularityConnector):
    product_name = "Identity"
