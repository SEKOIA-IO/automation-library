import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import orjson
from cachetools import LRUCache
from dateutil.parser import isoparse
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from nozomi_networks import NozomiModule
from nozomi_networks.client.event_type import EventType
from nozomi_networks.client.http_client import NozomiClient
from nozomi_networks.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


def _format_event(record: dict[str, Any]) -> dict[str, Any]:
    """
    Format Nozomi event.

    Args:
        record (dict[str, Any]): The record to extract the date from.

    Returns:
        datetime: The event date.
    """
    return {
        "id": record.get("id"),
        "event_type": record.get("type"),
        **record.get("attributes", {}),
    }


def _get_event_date(event: dict[str, Any]) -> datetime:
    """
    Each event contains `time` in unix timestamp format.

    Args:
        event:

    Returns:
        datetime:
    """
    event_time = event.get("time")
    if not event_time:
        raise ValueError(f"Event does not contain a valid time field: {event}")

    return datetime.fromtimestamp(int(event_time) / 1000, tz=timezone.utc)


class NozomiVantageConfiguration(DefaultConnectorConfiguration):
    """NozomiVantageConfiguration."""

    frequency: int = 600
    batch_size: int = 1000


class NozomiVantageConnector(AsyncConnector):
    """NozomiVantageConnector class to work with epdr events."""

    name = "NozomiVantageConnector"

    module: NozomiModule
    configuration: NozomiVantageConfiguration

    _nozomi_client: NozomiClient | None = None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init NozomiVantageConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._lru_caches: dict[EventType, LRUCache[str, int]] = {}
        with self.context as cache:
            for event_type in EventType:
                # Initialize caches from context if available
                existed_items = cache.get("caches", {}).get(event_type.name, [])
                self._lru_caches[event_type] = LRUCache(maxsize=1000)
                for event_id in existed_items:
                    self._lru_caches[event_type][event_id] = 1

    def _get_cache(self, event_type: EventType) -> LRUCache[str, int]:
        """
        Get the cache for the specified event type.

        Args:
            event_type (EventType): The type of event to get the cache for.

        Returns:
            LRUCache[str, int]: The cache for the specified event type.
        """
        if event_type not in self._lru_caches:
            # If the event type is not in the cache, create a new one
            self._lru_caches[event_type] = LRUCache(maxsize=1000)

        return self._lru_caches[event_type]

    def _add_events_to_cache(self, event_type: EventType, events: list[dict[str, Any]]) -> None:
        """
        Add an event ID to the cache for the specified event type.

        Args:
            event_type (EventType): The type of event.
            events (list[dict[str, Any]]): The list of events to add to the cache.
        """
        for event in events:
            event_id = event["id"]
            self._get_cache(event_type)[event_id] = 1

    def _is_new_event(self, event_type: EventType, event_id: str) -> bool:
        """
        Check if an event ID is new (not in the cache) for the specified event type.

        Args:
            event_type (EventType): The type of event.
            event_id (str): The ID of the event to check.

        Returns:
            bool: True if the event is new, False otherwise.
        """
        cache = self._get_cache(event_type)

        return event_id not in cache

    @property
    def nozomi_client(self) -> NozomiClient:
        """
        Get the Nozomi client.

        Returns:
            NozomiClient: The Nozomi client instance.
        """
        if self._nozomi_client is None:
            self._nozomi_client = NozomiClient(**self.module.configuration.dict())

        return self._nozomi_client

    def last_event_date(self, event_type: EventType) -> datetime:
        """
        Get last event date.

        Returns:
            datetime:
        """
        now = datetime.now(timezone.utc)
        one_day_ago = (now - timedelta(days=1)).replace(second=0, microsecond=0)

        with self.context as cache:  # pragma: no cover
            last_event_date_str = cache.get(event_type.name)

            # If undefined, retrieve events from the last 1 hour
            if last_event_date_str is None:
                return one_day_ago

            # Parse the most recent date seen
            last_event_date = isoparse(last_event_date_str).replace(microsecond=0)

            # We don't retrieve messages older than 1 hour
            return max(last_event_date, one_day_ago)

    async def get_events(self) -> int:
        total_records = 0
        for event_type in EventType:
            records = []
            last_event_date = self.last_event_date(event_type)
            logger.info(
                "Fetching events for {event_type} since {last_event_date}",
                event_type=event_type,
                last_event_date=last_event_date,
            )

            new_last_event_date = last_event_date
            async for event in self.nozomi_client.fetch_events(event_type, last_event_date):
                formated_event = _format_event(event)
                event_id = formated_event["id"]
                if not self._is_new_event(event_type, event_id):
                    continue

                event_date = _get_event_date(formated_event)
                if event_date <= last_event_date:
                    continue

                new_last_event_date = max(new_last_event_date, event_date)
                records.append(formated_event)

                if len(records) >= self.configuration.batch_size:
                    # If we have enough records, push them to intakes
                    total_pushed = len(
                        await self.push_data_to_intakes([orjson.dumps(record).decode("utf-8") for record in records])
                    )

                    logger.info(
                        "Total records pushed to intake: {total_pushed}. "
                        "Persisting into memory cache and updating new last event date for "
                        "{event_type} with {date_value}",
                        total_pushed=total_pushed,
                        event_type=event_type,
                        date_value=new_last_event_date.isoformat(),
                    )

                    total_records += total_pushed

                    self._add_events_to_cache(event_type, records)
                    records = []
                    with self.context as cache:
                        cache[event_type.name] = new_last_event_date.isoformat()

            if records:  # pragma: no cover
                total_pushed = len(
                    await self.push_data_to_intakes([orjson.dumps(record).decode("utf-8") for record in records])
                )

                logger.info(
                    "In IF: Total records pushed to intake: {total_pushed}. "
                    "Persisting into memory cache and updating new last event date for "
                    "{event_type} with {date_value}",
                    total_pushed=total_pushed,
                    event_type=event_type,
                    date_value=new_last_event_date.isoformat(),
                )

                total_records += total_pushed
                self._add_events_to_cache(event_type, records)

            # Update the last event date in the context
            with self.context as cache:
                cache[event_type.name] = new_last_event_date.isoformat()

        return total_records

    def run(self) -> None:  # pragma: no cover
        """Runs Nozomi Vantage."""
        while self.running:
            loop = asyncio.get_event_loop()

            try:
                previous_processing_end = None

                while self.running:
                    processing_start = time.time()
                    if previous_processing_end is not None:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
                            processing_start - previous_processing_end
                        )

                    events_count = loop.run_until_complete(self.get_events())
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
                message = "An error occurred while running Nozomi Vantage Connector: {error}"
                self.log_exception(error, message=message)

            with self.context as cache:
                cache["caches"] = {
                    event_type.name: list(cache.get(event_type.name, {}).keys()) for event_type in EventType
                }

            loop.run_until_complete(self.nozomi_client.close())
