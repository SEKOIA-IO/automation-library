"""Contains connector, configuration and module."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import TrellixHttpClient
from connectors import TrellixModule
from connectors.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class TrellixEpoConnectorConfig(DefaultConnectorConfiguration):
    """TellixEpoConnector configuration."""

    frequency: int = 300
    ratelimit_per_minute: int = 60
    ratelimit_per_day: int = 2000
    records_per_request: int = 100


class TrellixEpoConnector(AsyncConnector):
    """TrellixEpoConnector class to work with EDR events."""

    name = "TrellixEpoConnector"

    module: TrellixModule
    configuration: TrellixEpoConnectorConfig

    _trellix_client: TrellixHttpClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init TrellixEpoConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

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
    def trellix_client(self) -> TrellixHttpClient:
        """
        Get trellix client.

        Returns:
            TrellixHttpClient:
        """
        if self._trellix_client is not None:
            return self._trellix_client

        rate_limiter = AsyncLimiter(self.configuration.ratelimit_per_minute)
        daily_rate_limiter = AsyncLimiter(self.configuration.ratelimit_per_day)

        self._trellix_client = TrellixHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            api_key=self.module.configuration.api_key,
            auth_url=self.module.configuration.auth_url,
            base_url=self.module.configuration.base_url,
            rate_limiter=rate_limiter,
            rate_limiter_per_day=daily_rate_limiter,
        )

        return self._trellix_client

    async def get_trellix_epo_events(self) -> list[str]:
        """
        Process trellix epo events.

        Returns:
            List[str]:
        """
        events = await self.trellix_client.get_epo_events(
            self.last_event_date,
            self.configuration.records_per_request,
        )

        result: list[str] = await self.push_data_to_intakes(
            [orjson.dumps(event.attributes.dict()).decode("utf-8") for event in events]
        )

        return result

    async def async_run(self) -> None:  # pragma: no cover
        previous_processing_end: float | None = None

        while self.running:
            try:
                processing_start = time.time()
                if previous_processing_end is not None:
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                        processing_start - previous_processing_end
                    )

                message_ids: list[str] = await self.get_trellix_epo_events()
                processing_end = time.time()
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                log_message = "No records to forward"
                if len(message_ids) > 0:
                    log_message = "Pushed {0} records".format(len(message_ids))

                self.log(message=log_message, level="info")

                processing_time = processing_end - processing_start
                logger.info(
                    "Processing took {processing_time} seconds",
                    processing_time=processing_time,
                )

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(processing_time)

                # compute the remaining sleeping time. If greater than 0 and no messages where fetched, pause the connector
                delta_sleep = self.configuration.frequency - processing_time
                if len(message_ids) == 0 and delta_sleep > 0:
                    self.log(message=f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
                    await asyncio.sleep(delta_sleep)

            except Exception as e:
                self.log_exception(e, message="Error while running Trellix EPO")
                await asyncio.sleep(self.configuration.frequency)

    def run(self) -> None:  # pragma: no cover
        """Runs TrellixEdr."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())
