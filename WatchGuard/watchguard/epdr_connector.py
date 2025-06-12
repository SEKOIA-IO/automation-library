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

from watchguard import WatchGuardModule
from watchguard.client.http_client import WatchGuardClient, WatchGuardClientConfig
from watchguard.client.security_event import SecurityEvent
from watchguard.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


def _get_event_date(record: dict[str, Any]) -> datetime:
    """
    Get the event date from a record.

    Args:
        record (dict[str, Any]): The record to extract the date from.

    Returns:
        datetime: The event date.
    """
    date = record.get("security_event_date") or record.get("date")
    if not date:
        raise ValueError(f"Record does not contain a valid date field: {record}")

    return isoparse(date).astimezone(timezone.utc)


class WatchGuardEdrConnectorConfig(DefaultConnectorConfiguration):
    """WatchGuardEdrConnectorConfig."""

    frequency: int = 600


class WatchGuardEpdrConnector(AsyncConnector):
    """WatchGuardEpdrConnector class to work with epdr events."""

    name = "WatchGuardEpdrConnector"

    module: WatchGuardModule
    configuration: WatchGuardEdrConnectorConfig

    _watchguard_client: WatchGuardClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init WatchGuardEpdrConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def watchguard_client(self) -> WatchGuardClient:
        """
        Get the WatchGuard client.

        Returns:
            WatchGuardClient: The WatchGuard client instance.
        """
        if self._watchguard_client is None:
            config = WatchGuardClientConfig(**self.module.configuration.dict())
            self._watchguard_client = WatchGuardClient(config)

        return self._watchguard_client

    def last_event_date(self, security_event: SecurityEvent) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = (now - timedelta(hours=1)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get(security_event.name)

            # If undefined, retrieve events from the last 1 hour
            if last_event_date_str is None:
                return one_hour_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

            # We don't retrieve messages older than 1 hour
            if last_event_date < one_hour_ago:
                return one_hour_ago

            return last_event_date

    async def get_watchguard_events(self) -> int:
        total_records = 0
        for security_event in SecurityEvent:
            records = []
            last_event_date = self.last_event_date(security_event)
            logger.info(
                "Fetching events for {security_event.name} since {last_event_date}",
                security_event=security_event,
                last_event_date=last_event_date,
            )
            new_last_event_date = last_event_date
            async for record in self.watchguard_client.fetch_data(security_event, period=1):
                event_date = _get_event_date(record)
                if event_date <= last_event_date:
                    continue

                new_last_event_date = max(new_last_event_date, event_date)
                records.append(record)

            logger.info(
                "Records count to push for {security_event.name}: {count}",
                security_event=security_event,
                count=len(records),
            )

            if records:
                total_records += len(
                    await self.push_data_to_intakes([orjson.dumps(record).decode("utf-8") for record in records])
                )

            # Update the last event date in the context
            with self.context as cache:
                cache[security_event.name] = new_last_event_date.isoformat()

        return total_records

    def run(self) -> None:  # pragma: no cover
        """Runs WatchGuard EPDR."""
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

                    events_count = loop.run_until_complete(self.get_watchguard_events())
                    processing_end = time.time()
                    OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(events_count)

                    log_message = "No records to forward"
                    if events_count > 0:
                        log_message = "Pushed {0} records".format(events_count)

                    logger.info(log_message)
                    self.log(message=log_message, level="info")

                    batch_duration = processing_end - processing_start
                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)

                    # If no records were fetched
                    if events_count == 0:
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
                logger.error("Error while running Watchguard EPDR: {error}", error=error)
                self.log_exception(error, message="Failed to forward events")
