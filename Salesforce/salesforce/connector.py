"""Contains connector, configuration and module."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import LogType, SalesforceHttpClient
from salesforce import SalesforceModule
from salesforce.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from utils.file_utils import csv_file_as_rows, delete_file


class SalesforceConnectorConfig(DefaultConnectorConfiguration):
    """SalesforceConnector configuration."""

    frequency: int = 600
    fetch_daily_logs: bool = False

    @property
    def log_type(self) -> LogType:
        """Get log type."""
        return LogType.DAILY if self.fetch_daily_logs else LogType.HOURLY


class SalesforceConnector(AsyncConnector):
    """SalesforceConnector class to work with salesforce events."""

    name = "SalesforceConnector"

    module: SalesforceModule
    configuration: SalesforceConnectorConfig

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
    def salesforce_client(self) -> SalesforceHttpClient:
        """
        Get salesforce client.

        Returns:
            SalesforceHttpClient:
        """
        if self._salesforce_client is not None:
            return self._salesforce_client

        self._salesforce_client = SalesforceHttpClient(
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            base_url=self.module.configuration.base_url,
            rate_limiter=self.module.configuration.rate_limiter,
        )

        return self._salesforce_client

    async def get_salesforce_events(self) -> list[str]:
        """
        Process salesforce events.

        Returns:
            datetime: last event date
        """
        _last_event_date = self.last_event_date
        log_files = await self.salesforce_client.get_log_files(_last_event_date, self.configuration.log_type)

        logger.info(
            "Found {count} log files to process since {date}",
            count=len(log_files.records),
            date=_last_event_date.isoformat(),
        )

        result = []

        for log_file in log_files.records:
            log_file_results = []
            log_file_date = isoparse(log_file.CreatedDate)
            if _last_event_date < log_file_date:
                _last_event_date = log_file_date

            records, csv_path = await self.salesforce_client.get_log_file_content(
                log_file=log_file,
            )

            if records is not None:
                log_file_results.extend(
                    await self.push_data_to_intakes([orjson.dumps(event).decode("utf-8") for event in records])
                )

            # Process csv file row by row to avoid memory issues
            if csv_path is not None:
                async for row in csv_file_as_rows(csv_path):
                    log_file_results.extend(await self.push_data_to_intakes([orjson.dumps(row).decode("utf-8")]))

                await delete_file(csv_path)

            logger.info(
                "Finished to process log file {log_file_id}. Total amount of records is {count}",
                log_file_id=log_file.Id,
                count=len(log_file_results),
            )

            result.extend(log_file_results)

            with self.context as cache:
                logger.info(
                    "New last event date now is {last_event_date}",
                    last_event_date=_last_event_date.isoformat(),
                )

                cache["last_event_date"] = _last_event_date.isoformat()

        return result

    def run(self) -> None:  # pragma: no cover
        """Runs Salesforce."""
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                previous_processing_end = None

                while self.running:
                    processing_start = time.time()
                    if previous_processing_end is not None:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                            processing_start - previous_processing_end
                        )

                    message_ids: list[str] = loop.run_until_complete(self.get_salesforce_events())
                    processing_end = time.time()
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = "Pushed {0} records".format(len(message_ids))

                    logger.info(log_message)
                    self.log(message=log_message, level="info")

                    batch_duration = processing_end - processing_start
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

                    # If no records were fetched
                    if len(message_ids) == 0:
                        # compute the remaining sleeping time. If greater than 0, sleep
                        delta_sleep = self.configuration.frequency - batch_duration
                        if delta_sleep > 0:
                            self.log(
                                message=f"Next batch of events in the future. " f"Waiting {delta_sleep} seconds",
                                level="info",
                            )
                            time.sleep(delta_sleep)

                    previous_processing_end = processing_end

            except Exception as error:
                logger.error("Error while running Salesforce: {error}", error=error)
                self.log_exception(error, message="Failed to forward events")
