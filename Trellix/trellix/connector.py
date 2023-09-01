"""Contains connector, configuration and module."""
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from pydantic import HttpUrl
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from client.http_client import TrellixHttpClient

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class TrellixConfig(DefaultConnectorConfiguration):
    """Configuration for TrellixConnector."""

    client_id: str
    client_secret: str
    api_key: str
    delay: int = 60
    ratelimit_per_minute: int = 60
    records_per_request: int = 100
    auth_url: HttpUrl = HttpUrl("https://iam.mcafee-cloud.com/iam/v1.1", scheme="https")
    base_url: HttpUrl = HttpUrl("https://api.manage.trellix.com", scheme="https")


class TrellixModule(Module):
    """TrellixModule."""

    pass


class TrellixEdrConnector(Connector):
    """TrellixEdrConnector class to work with EDR events."""

    name = "TrellixEdrConnector"

    module: TrellixModule
    configuration: TrellixConfig

    _trellix_client: TrellixHttpClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init TrellixEdrConnector."""

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

        self._trellix_client = TrellixHttpClient(
            client_id=self.configuration.client_id,
            client_secret=self.configuration.client_secret,
            api_key=self.configuration.api_key,
            auth_url=self.configuration.auth_url,
            base_url=self.configuration.base_url,
            rate_limiter=rate_limiter,
        )

        return self._trellix_client

    async def _push_events(self, events: list[str]) -> list[str]:
        """
        Push events to intakes.

        Simple wrapper over `self.push_events_to_intakes` to run it async.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return await asyncio.to_thread(
            self.push_events_to_intakes,
            events=events,
            sync=True,
        )

    async def get_trellix_edr_events(self) -> List[str]:
        """
        Process trellix edr events.

        Returns:
            List[str]:
        """
        events = await self.trellix_client.get_epo_events(
            self.last_event_date,
            self.configuration.records_per_request,
        )

        return await self._push_events([orjson.dumps(event.attributes.dict()).decode("utf-8") for event in events])

    def run(self) -> None:
        """Runs TrellixEdr."""
        previous_processing_end = None

        try:
            loop = asyncio.get_event_loop()

            while True:
                processing_start = time.time()
                if previous_processing_end is not None:
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                        processing_start - previous_processing_end
                    )

                message_ids: list[str] = loop.run_until_complete(self.get_trellix_edr_events())
                processing_end = time.time()
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                log_message = "No records to forward"
                if len(message_ids) > 0:
                    log_message = "Pushed {0} records".format(len(message_ids))

                logger.info(log_message)
                self.log(message=log_message, level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    processing_end - processing_start
                )

                previous_processing_end = processing_end

                loop.run_until_complete(asyncio.sleep(self.configuration.delay))

        except Exception as e:
            logger.error("Error while running TrellixEdr: {error}", error=e)
