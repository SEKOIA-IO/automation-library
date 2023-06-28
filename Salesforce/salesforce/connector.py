"""Contains connector, configuration and module."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from pydantic import HttpUrl
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from client.http_client import SalesforceHttpClient
from utils.file_utils import csv_file_as_rows, delete_file

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class SalesforceConfig(DefaultConnectorConfiguration):
    """Configuration for SalesforceConnector."""

    client_id: str
    client_secret: str
    base_url: HttpUrl
    ratelimit_per_minute: int = 60


class SalesforceModule(Module):
    """SalesforceConfig."""

    configuration: SalesforceConfig


class SalesforceConnector(Connector):
    """SalesforceConnector class to work with salesforce events."""

    name = "SalesforceConnector"

    module: SalesforceModule

    _salesforce_client: SalesforceHttpClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init SalesforceConnector."""

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
        one_week_ago = (now - timedelta(hours=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 7 days
            if last_event_date_str is None:
                return one_week_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

            # We don't retrieve messages older than one week
            if last_event_date < one_week_ago:
                return one_week_ago

            return last_event_date

    @property
    def salesforce_client(self) -> SalesforceHttpClient:
        """
        Get salesforce client.

        Returns:
            SalesforceHttpClient:
        """
        if self._salesforce_client is not None:
            return self._salesforce_client

        rate_limiter = AsyncLimiter(self.module.configuration.ratelimit_per_minute)

        self._salesforce_client = SalesforceHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            base_url=self.module.configuration.base_url,
            rate_limiter=rate_limiter,
        )

        return self._salesforce_client

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

    async def get_salesforce_events(self) -> list[str]:
        """
        Process salesforce events.

        Returns:
            datetime: last event date
        """
        _last_event_date = self.last_event_date
        log_files = await self.salesforce_client.get_log_files(_last_event_date.isoformat())

        logger.info(
            "Found {count} log files to process since {date}",
            count=len(log_files.records),
            date=_last_event_date.isoformat(),
        )

        result = []

        for log_file in log_files.records:
            log_file_date = isoparse(log_file.LogDate)
            if _last_event_date < log_file_date:
                _last_event_date = log_file_date

            records, csv_path = await self.salesforce_client.get_log_file_content(
                log_file_uri=log_file.LogFile,
            )

            if records is not None:
                result.extend(await self._push_events([orjson.dumps(event).decode("utf-8") for event in records]))

            # Process csv file row by row to avoid memory issues
            if csv_path is not None:
                async for row in csv_file_as_rows(csv_path):
                    result.extend(await self._push_events([orjson.dumps(row).decode("utf-8")]))

                await delete_file(csv_path)

            with self.context as cache:
                cache["last_event_date"] = _last_event_date.isoformat()

        return result

    def run(self) -> None:
        """Runs TrellixEdr."""
        loop = asyncio.get_event_loop()

        previous_processing_end = None
        try:
            while True:
                processing_start = time.time()
                if previous_processing_end is not None:
                    EVENTS_LAG.labels(intake_key=self.module.configuration.intake_key).observe(
                        processing_start - previous_processing_end
                    )

                message_ids: list[str] = loop.run_until_complete(self.get_salesforce_events())
                processing_end = time.time()
                OUTCOMING_EVENTS.labels(intake_key=self.module.configuration.intake_key).inc(len(message_ids))

                log_message = "No records to forward"
                if len(message_ids) > 0:
                    log_message = "Pushed {0} records".format(len(message_ids))

                logger.info(log_message)
                self.log(message=log_message, level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.module.configuration.intake_key).observe(
                    processing_end - processing_start
                )

                previous_processing_end = processing_end

        except Exception as e:
            logger.error("Error while running TrellixEdr: {error}", error=e)

        finally:
            loop.close()
