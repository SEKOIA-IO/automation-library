import asyncio
import time
from abc import ABC
from datetime import datetime, timedelta, timezone
from functools import cached_property
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from sentinelone_module.base import SentinelOneModule
from sentinelone_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from sentinelone_module.singularity.client import SingularityClient


class SingularityConnectorConfig(DefaultConnectorConfiguration):
    """Configuration for SingularityConnector."""

    frequency: int = 60


class AbstractSingularityConnector(AsyncConnector, ABC):
    module: SentinelOneModule
    configuration: SingularityConnectorConfig

    product_name: str

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON(f"{self.product_name}_context.json", self._data_path)

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

    @property
    def last_event_date(self) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_week_ago = (now - timedelta(days=7)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 7 days
            if last_event_date_str is None:
                return one_week_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str)

            # We don't retrieve messages older than one week
            if last_event_date < one_week_ago:
                return one_week_ago

            return last_event_date

    @property
    def last_checkpoint(self) -> str | None:
        with self.context as cache:
            result: str | None = cache.get("last_checkpoint")

            return result

    async def single_run(self) -> int:
        result = 0

        while True:
            last_event_date = self.last_event_date
            data = await self.client.list_alerts(
                product_name=self.product_name,
                after=self.last_checkpoint,
                start_time=last_event_date.timestamp(),
            )

            pushed_events = await self.push_data_to_intakes(
                [orjson.dumps(alert).decode("utf-8") for alert in data.alerts]
            )
            result += len(pushed_events)

            for alert in data.alerts:
                alert_detected_at = isoparse(alert["detectedAt"])
                if alert_detected_at > last_event_date:
                    last_event_date = alert_detected_at

            with self.context as cache:
                cache["last_event_date"] = last_event_date.isoformat()
                cache["last_checkpoint"] = data.end_cursor

            if not data.has_next_page:
                break

        return result

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                processing_start = time.time()
                result = await self.single_run()
                last_event_date = self.last_event_date
                processing_end = time.time()

                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
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
    product_name = "identity"
