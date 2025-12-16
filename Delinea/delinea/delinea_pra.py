import asyncio
import time
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any, Optional

import orjson
from cachetools import Cache, LRUCache
from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from delinea import DelineaModule
from delinea.client.delinea_client import DelineaClient
from delinea.metrics import FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class DelineaPraConnectorConfig(DefaultConnectorConfiguration):
    frequency: int = 60
    chunk_size: int = 1000


class DelineaPraConnector(AsyncConnector):
    name = "DelineaPraConnector"
    module: DelineaModule
    configuration: DelineaPraConnectorConfig

    _client: DelineaClient | None

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init DelineaPraConnector."""

        super().__init__(*args, **kwargs)
        self._client = None
        self.context = PersistentJSON("context.json", self._data_path)
        self.last_event_date = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=7),
        )

        self.events_cache = self.load_cache(maxsize=500)

    def load_cache(self, maxsize: int) -> Cache[str, bool]:
        result: LRUCache[str, bool] = LRUCache(maxsize=maxsize)

        with self.context as cache:
            events_ids = cache.get("cached_events", [])

        for event_id in events_ids:
            result[event_id] = True

        return result

    def save_cache(self) -> None:
        with self.context as cache:
            cache["cached_events"] = list(self.events_cache.keys())

    @cached_property
    def client(self) -> DelineaClient:
        if not self._client:
            self._client = DelineaClient(
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
                base_url=self.module.configuration.base_url,
            )

        return self._client

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())

    async def get_events(self) -> int:
        total_events = 0
        start_date = self.last_event_date.offset
        end_date = datetime.now()

        new_start_date = start_date

        events: list[dict[str, Any]] = []
        async for event in self.client.get_audit_events(start_date, end_date):
            event_id = event.get("eventMessageId")
            if event_id and event_id in self.events_cache:
                continue

            # format is '2025-09-18T13:34:17.603+00:00'
            event_date = event.get("eventDateTime")
            if event_date:
                event_date = datetime.fromisoformat(event_date)
                new_start_date = max(new_start_date, event_date)

            events.append(event)
            if len(events) >= self.configuration.chunk_size:
                await self.push_data_to_intakes([orjson.dumps(value).decode() for value in events])
                total_events += len(events)
                events = []
                self.save_cache()
                self.last_event_date.offset = new_start_date

        if len(events) > 0:
            await self.push_data_to_intakes([orjson.dumps(value).decode() for value in events])
            total_events += len(events)
            self.save_cache()
            self.last_event_date.offset = new_start_date

        if total_events > 0:
            self.log(message=f"Fetched {total_events} events from Delinea PRA", level="info")
        else:
            self.log(message="No new events fetched from Delinea PRA", level="info")

        return total_events

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                duration_start = time.time()

                results = await self.get_events()
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(results)

                # compute the duration of the last events fetching
                duration = int(time.time() - duration_start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                # sleep if no events were fetched
                data_sleep = self.configuration.frequency - duration
                if len(results) == 0 and data_sleep > 0:
                    logger.info(f"Next batch in the future. Sleeping for {data_sleep} seconds.")
                    await asyncio.sleep(data_sleep)

            except Exception as e:
                logger.error(f"Error while running Delinea PRA: {e}", error=e)
                self.log_exception(e)

        if self._client:
            await self._client.close()
            self._client = None


