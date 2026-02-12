"""Contains connector, configuration and module."""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import LogType, SalesforceHttpClient
from client.token_refresher import RefreshTokenException
from salesforce import SalesforceModule
from salesforce.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
from salesforce.timestepper import TimeStepper
from utils.file_utils import csv_file_as_rows, delete_file


class SalesforceConnectorConfig(DefaultConnectorConfiguration):
    """SalesforceConnector configuration."""

    frequency: int = 600
    initial_hours_ago: int = 6
    timedelta: int = 15
    fetch_daily_logs: bool = False

    @property
    def log_type(self) -> LogType | None:
        """Get log type."""
        return None if self.fetch_daily_logs else LogType.HOURLY


class SalesforceConnector(AsyncConnector):
    """SalesforceConnector class to work with salesforce events."""

    name = "SalesforceConnector"

    module: SalesforceModule
    configuration: SalesforceConnectorConfig

    _salesforce_client: SalesforceHttpClient | None = None
    _stepper: TimeStepper | None = None

    # Maximum history limit for recovery (in days)
    MAX_HISTORY_DAYS = 30

    # LRU cache size for processed log file IDs
    # 100 is more then enough because we persist log file ids and not event ids itself
    LOG_FILE_CACHE_SIZE = 100

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init SalesforceConnector."""
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

        log_file_cache_size = int(os.getenv("LOG_FILE_CACHE_SIZE", 100))
        self.log_file_cache: Cache[str, bool] = self._load_log_file_cache(log_file_cache_size)

    @property
    def stepper(self) -> TimeStepper:
        """
        Get or create the timestepper.

        Recovers from cache if available, otherwise creates new with hours_ago lookback.
        The instance is cached to prevent recreation on each access.

        Returns:
            TimeStepper instance
        """
        if self._stepper is not None:
            return self._stepper

        with self.context as cache:
            most_recent_date_str = cache.get("last_event_date")

        if most_recent_date_str is None:
            self._stepper = TimeStepper.create(
                self,
                self.configuration.frequency,
                self.configuration.timedelta,
                self.configuration.initial_hours_ago,
            )

            return self._stepper

        # Parse the most recent requested date
        most_recent_date = isoparse(most_recent_date_str)

        # Enforce maximum history limit
        now = datetime.now(timezone.utc)
        max_history_date = now - timedelta(days=self.MAX_HISTORY_DAYS)
        if most_recent_date < max_history_date:
            most_recent_date = max_history_date

        self._stepper = TimeStepper.create_from_time(
            self,
            most_recent_date,
            self.configuration.frequency,
            self.configuration.timedelta,
        )
        return self._stepper

    def update_stepper(self, recent_date: datetime) -> None:
        """
        Save the most recent date processed.

        Args:
            recent_date: End datetime of the last processed window
        """
        with self.context as cache:
            cache["last_event_date"] = recent_date.isoformat()

    def _load_log_file_cache(self, cache_size: int = 100) -> Cache[str, bool]:
        """
        Load log file IDs from persistent storage into LRU cache.

        Returns:
            LRUCache with previously processed log file IDs
        """
        result: Cache[str, bool] = LRUCache(maxsize=cache_size)

        with self.context as cache:
            log_file_ids = cache.get("processed_log_files", [])

        # Will keep latest files always in the cache
        for log_file_id in reversed(log_file_ids):
            result[log_file_id] = True

        return result

    def _save_log_file_cache(self) -> None:
        """Persist the LRU cache to storage."""
        with self.context as cache:
            cache["processed_log_files"] = list(self.log_file_cache.keys())

    def is_log_file_processed(self, log_file_id: str) -> bool:
        """
        Check if a log file has already been processed.

        Args:
            log_file_id: The Salesforce log file ID

        Returns:
            True if the log file was already processed
        """
        return log_file_id in self.log_file_cache

    def mark_log_file_processed(self, log_file_id: str) -> None:
        """
        Mark a log file as processed.

        Args:
            log_file_id: The Salesforce log file ID
        """
        self.log_file_cache[log_file_id] = True

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

    async def get_salesforce_events(self, start: datetime, end: datetime) -> list[str]:
        """
        Process salesforce events for a specific time window.

        Args:
            start: Start of time window (exclusive)
            end: End of time window (inclusive)

        Returns:
            List of message IDs pushed to intake
        """
        log_files = await self.salesforce_client.get_log_files(
            start_from=start,
            end_at=end,
            log_type=self.configuration.log_type,
        )

        logger.info(
            "Found {count} log files to process for window {start} to {end}",
            count=len(log_files.records),
            start=start.isoformat(),
            end=end.isoformat(),
        )

        result = []

        for log_file in log_files.records:
            # Check if already processed
            if self.is_log_file_processed(log_file.Id):
                logger.info(
                    "Skipping already processed log file {log_file_id}",
                    log_file_id=log_file.Id,
                )
                continue

            log_file_results = []

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
                "Finished processing log file {log_file_id}. Total records: {count}",
                log_file_id=log_file.Id,
                count=len(log_file_results),
            )

            # Mark as processed
            self.mark_log_file_processed(log_file.Id)
            result.extend(log_file_results)

        return result

    def run(self) -> None:  # pragma: no cover
        """Runs Salesforce connector with timestepper."""
        while self.running:
            try:
                loop = asyncio.get_event_loop()

                for start, end in self.stepper.ranges():
                    if not self.running:
                        break

                    processing_start = time.time()

                    message_ids: list[str] = loop.run_until_complete(self.get_salesforce_events(start, end))

                    processing_end = time.time()
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                    log_message = "No records to forward"
                    if len(message_ids) > 0:
                        log_message = f"Pushed {len(message_ids)} records"

                    logger.info(log_message)
                    self.log(message=log_message, level="info")

                    batch_duration = processing_end - processing_start
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

                    # Save progress after each window
                    self.update_stepper(end)
                    self._save_log_file_cache()

            except RefreshTokenException as error:
                logger.error("Error while running Salesforce", error=error)
                self.log(message="Using refresh token failed. Please check the credentials", level="critical")

            except Exception as error:
                logger.error("Error while running Salesforce", error=error)
                self.log_exception(error, message="Failed to forward events")
