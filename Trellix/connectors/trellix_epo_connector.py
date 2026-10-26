"""Contains connector, configuration and module."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
from aiolimiter import AsyncLimiter
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from client.http_client import TrellixHttpClient
from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.trellix_response import TrellixResponse
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

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
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
        now = datetime.now(UTC)
        one_week_ago = (now - timedelta(days=7)).replace(microsecond=0)

        with self.context as cache:
            last_event_date_str = cache.get("last_event_date")

            # If undefined, retrieve events from the last 7 days
            if last_event_date_str is None:
                return one_week_ago

            # Parse the most recent date seen
            last_event_date: datetime = isoparse(last_event_date_str)

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
            auth_url=str(self.module.configuration.auth_url).rstrip("/"),
            base_url=str(self.module.configuration.base_url).rstrip("/"),
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

        # The API filter is `timestamp GT <checkpoint truncated to the second>`,
        # so events of the checkpoint second are returned again: skip those already forwarded.
        with self.context as cache:
            boundary_event_ids = set(cache.get("last_event_ids") or [])

        new_events = [event for event in events if self._event_id(event) not in boundary_event_ids]

        result: list[str] = []
        if new_events:
            result = await self.push_data_to_intakes(
                [orjson.dumps(event.attributes.model_dump()).decode("utf-8") for event in new_events]
            )

        # Save the checkpoint only once the events have been pushed.
        # The SDK raises when the intake rejects a chunk (after its retries), so the checkpoint is not reached then.
        self._save_checkpoint(events, boundary_event_ids)

        return result

    @staticmethod
    def _event_id(event: TrellixResponse[EpoEventAttributes]) -> str | None:
        return event.id or event.attributes.autoguid

    @staticmethod
    def _event_timestamp(event: TrellixResponse[EpoEventAttributes]) -> datetime | None:
        timestamp = event.attributes.timestamp
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        return timestamp

    def _save_checkpoint(
        self, events: list[TrellixResponse[EpoEventAttributes]], boundary_event_ids: set[str]
    ) -> None:
        """
        Save the most recent event timestamp and the ids of the events of that second.

        Args:
            events: list[TrellixResponse[EpoEventAttributes]]
            boundary_event_ids: set[str]
        """
        timestamps = [timestamp for event in events if (timestamp := self._event_timestamp(event)) is not None]
        if not timestamps:
            return

        most_recent_date = max(timestamps)
        if most_recent_date < self.last_event_date:
            return

        most_recent_second = most_recent_date.replace(microsecond=0)
        last_event_ids = {
            event_id
            for event in events
            if (timestamp := self._event_timestamp(event)) is not None
            and timestamp.replace(microsecond=0) == most_recent_second
            and (event_id := self._event_id(event)) is not None
        }
        # Keep the ids already seen when the checkpoint stays in the same second
        if self.last_event_date.replace(microsecond=0) == most_recent_second:
            last_event_ids |= boundary_event_ids

        with self.context as cache:
            cache["last_event_date"] = most_recent_date.isoformat()
            cache["last_event_ids"] = sorted(last_event_ids)

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
                    log_message = f"Pushed {len(message_ids)} records"

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
