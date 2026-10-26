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
from yarl import URL

from client.http_client import EpoEventsPage, TrellixHttpClient
from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.trellix_response import TrellixResponse
from connectors import TrellixModule
from connectors.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

# Soft bound on the number of pages read in one run (see `get_trellix_epo_events`)
MAX_PAGES_PER_RUN = 100
# Bound on the number of ids of the checkpoint second kept in context.json for deduplication
MAX_LAST_EVENT_IDS = 10_000


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
        Collect and forward all the available trellix epo events.

        Pages are read inside one `GT <checkpoint second>` window sorted by ascending timestamp, following
        `links.next` when the API returns it and using `page[offset]` otherwise. Each page is pushed, then the
        checkpoint is saved, so a failure loses nothing and only re-reads the pages not saved yet.

        Returns:
            List[str]: the ids of the forwarded events
        """
        start_date = self.last_event_date
        start_second = start_date.replace(microsecond=0)
        limit = self.configuration.records_per_request

        offset = 0
        next_url: URL | None = None
        pages = 0
        # Ids forwarded during this run, to skip events moved to a later page by a concurrent insertion
        seen_event_ids: set[str] = set()
        result: list[str] = []

        while self.running:
            page = await self.trellix_client.get_epo_events_page(start_date, limit, offset, url=next_url)
            pages += 1

            # The API filter is `timestamp GT <checkpoint truncated to the second>`,
            # so events of the checkpoint second are returned again: skip those already forwarded.
            with self.context as cache:
                boundary_event_ids = set(cache.get("last_event_ids") or [])

            new_events: list[TrellixResponse[EpoEventAttributes]] = []
            for event in page.events:
                event_id = self._event_id(event)
                if event_id is not None:
                    if event_id in boundary_event_ids or event_id in seen_event_ids:
                        continue
                    seen_event_ids.add(event_id)

                new_events.append(event)

            if new_events:
                pushed_ids = await self.push_data_to_intakes(
                    [orjson.dumps(event.attributes.model_dump()).decode("utf-8") for event in new_events]
                )
                result.extend(pushed_ids)
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(pushed_ids))

            # Save the checkpoint only once the events have been pushed.
            # The SDK raises when the intake rejects a chunk (after its retries), so the checkpoint is not reached then.
            self._save_checkpoint(page.events)

            logger.info(
                "Trellix ePO page {page} (offset {offset}): {count} events, {new} forwarded",
                page=pages,
                offset=offset,
                count=len(page.events),
                new=len(new_events),
            )

            if not self._has_next_page(page, limit):
                break

            # Stop at the per-run bound, but only once the checkpoint left the second the run started from:
            # the next run then starts from a new window. Otherwise, a second holding more events than one run
            # can read would be read again from its first page at every run, and the connector would be stuck.
            if pages >= MAX_PAGES_PER_RUN and self.last_event_date.replace(microsecond=0) > start_second:
                self.log(
                    message=f"Read {pages} pages in this run, the next run continues from the checkpoint",
                    level="info",
                )
                break

            offset += limit
            next_url = page.next_url

        return result

    @staticmethod
    def _has_next_page(page: EpoEventsPage, limit: int) -> bool:
        """
        Tell whether another page must be read.

        Args:
            page: EpoEventsPage
            limit: int

        Returns:
            bool:
        """
        if not page.events:
            return False

        # A JSON:API `links` object is authoritative: no `next` link means no more pages
        if page.has_links:
            return page.next_url is not None

        return len(page.events) >= limit

    @staticmethod
    def _event_id(event: TrellixResponse[EpoEventAttributes]) -> str | None:
        return event.id or event.attributes.autoguid

    @staticmethod
    def _event_timestamp(event: TrellixResponse[EpoEventAttributes]) -> datetime | None:
        timestamp = event.attributes.timestamp
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        return timestamp

    def _save_checkpoint(self, events: list[TrellixResponse[EpoEventAttributes]]) -> None:
        """
        Save the most recent event timestamp and the ids of the events of that second.

        The checkpoint never moves backward. The ids of the checkpoint second are merged with those already
        saved while the checkpoint stays in that second, and capped to the `MAX_LAST_EVENT_IDS` most recent.

        Args:
            events: list[TrellixResponse[EpoEventAttributes]]
        """
        timestamps = [timestamp for event in events if (timestamp := self._event_timestamp(event)) is not None]
        if not timestamps:
            return

        current_date = self.last_event_date
        checkpoint_date = max(current_date, max(timestamps))
        checkpoint_second = checkpoint_date.replace(microsecond=0)

        page_event_ids: list[str] = []
        for event in events:
            timestamp = self._event_timestamp(event)
            event_id = self._event_id(event)
            if (
                timestamp is not None
                and event_id is not None
                and timestamp.replace(microsecond=0) == checkpoint_second
            ):
                page_event_ids.append(event_id)

        with self.context as cache:
            # Keep the ids already seen when the checkpoint stays in the same second
            last_event_ids: list[str] = []
            if current_date.replace(microsecond=0) == checkpoint_second:
                last_event_ids = list(cache.get("last_event_ids") or [])

            known_ids = set(last_event_ids)
            for event_id in page_event_ids:
                if event_id not in known_ids:
                    known_ids.add(event_id)
                    last_event_ids.append(event_id)

            cache["last_event_date"] = checkpoint_date.isoformat()
            cache["last_event_ids"] = last_event_ids[-MAX_LAST_EVENT_IDS:]

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
