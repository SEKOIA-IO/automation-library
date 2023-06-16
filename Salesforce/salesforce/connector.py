"""Contains connector, configuration and module."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiocsv
import aiofiles
from aiofiles import os as aiofiles_os
import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from pydantic import HttpUrl
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from client.http_client import SalesforceHttpClient


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
        self.from_date = self.last_event_date

    @property
    def last_event_date(self) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # if undefined, retrieve events from the last 7 days
            if last_event_date_str is None:
                return one_week_ago

            # parse the most recent date seen
            last_event_date = isoparse(last_event_date_str)

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

    @staticmethod
    async def _delete_file(file_name: str) -> None:
        """
        Delete file.

        Args:
            file_name: str
        """
        await aiofiles_os.remove(file_name)

    async def _push_events(self, events: list[str]) -> None:
        """
        Push events to intakes.

        Simple wrapper over `self.push_events_to_intakes` to run it async.

        Args:
            events: list[str]
        """
        await asyncio.to_thread(
            self.push_events_to_intakes,
            events=[orjson.dumps(event).decode("utf-8") for event in events],
            sync=True,
        )

    async def get_salesforce_events(self) -> datetime | None:
        """
        Process salesforce events.

        Returns:
            datetime: last event date
        """
        last_event_date = None
        log_files = await self.salesforce_client.get_log_files(self.from_date.isoformat())
        for log_file in log_files.records:
            log_file_date = isoparse(log_file.LogDate)
            if last_event_date is None or last_event_date < log_file_date:
                last_event_date = log_file_date

            records, csv_path = await self.salesforce_client.get_log_file_content(
                log_file_uri=log_file.LogFile,
            )

            if records is not None:
                await self._push_events([orjson.dumps(event).decode("utf-8") for event in records])

            # Process csv file row by row to avoid memory issues
            if csv_path is not None:
                async with aiofiles.open(csv_path, encoding="utf-8") as file:
                    async for row in aiocsv.AsyncDictReader(file, delimiter=","):
                        await self._push_events([orjson.dumps(row).decode("utf-8")])

                await self._delete_file(csv_path)

            if last_event_date > self.from_date:
                self.from_date = last_event_date

            with self.context as cache:
                cache["last_event_date"] = last_event_date.isoformat()

        return last_event_date

    def run(self) -> None:
        """Runs Salesforce connector."""
        loop = asyncio.get_event_loop()

        try:
            while self.running:
                loop.run_until_complete(self.get_salesforce_events())

        except Exception as e:
            logger.error("Error while running SalesforceConnector: {error}", error=e)

        finally:
            loop.close()
