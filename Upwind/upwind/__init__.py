import asyncio
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
from cachetools import Cache, LRUCache
from dateutil.parser import isoparse
from pydantic.v1 import BaseModel, HttpUrl, SecretStr
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import DefaultConnectorConfiguration
from sekoia_automation.module import Module


class UpwindModuleConfig(BaseModel):
    base_url: HttpUrl
    api_token: SecretStr
    organization_id: str


class UpwindModule(Module):
    configuration: UpwindModuleConfig


class UpwindConnectorConfig(DefaultConnectorConfiguration):
    frequency: int = 60
    page_size: int = 100


@dataclass
class UpwindPage:
    items: list[dict[str, Any]]
    next_page_token: str | None = None


class UpwindConnector(AsyncConnector):
    configuration: UpwindConnectorConfig
    module: UpwindModule

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        super().__init__(*args, **kwargs)
        self.last_event_date = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=30),
        )
        self.events_cache: Cache = LRUCache(maxsize=10000)
        self.request_timeout = int(os.environ.get("UPWIND_CLIENT_TIMEOUT", "60"))

    async def fetch_page(self, since: datetime, page_token: str | None = None) -> UpwindPage:
        raise NotImplementedError

    async def single_run(self) -> int:
        since = self.last_event_date.offset
        max_seen = since
        total_sent = 0
        next_page_token: str | None = None

        while True:
            page = await self.fetch_page(since=since, page_token=next_page_token)
            if not page.items:
                break

            new_events = filter_new_events(page.items, self.events_cache)
            outgoing: list[str] = []
            for event in new_events:
                outgoing.append(orjson.dumps(event).decode("utf-8"))

                event_dt = extract_upwind_detection_datetime(event)
                if event_dt and event_dt > max_seen:
                    max_seen = event_dt

            if outgoing:
                pushed = await self.push_data_to_intakes(outgoing)
                total_sent += len(pushed)

            next_page_token = page.next_page_token
            if not next_page_token:
                break

        self.last_event_date.offset = max_seen
        return total_sent

    async def async_run(self) -> None:  # pragma: no cover
        while self.running:
            try:
                started = time.time()
                pushed_count = await self.single_run()
                duration = time.time() - started

                if pushed_count > 0:
                    self.log(message=f"Pushed {pushed_count} records in {duration:.2f}s", level="info")
                else:
                    self.log(message="No records to forward", level="info")

                wait_time = max(0.0, self.configuration.frequency - duration)
                await asyncio.sleep(wait_time)

            except Exception as error:
                self.log_exception(error)
                await asyncio.sleep(self.configuration.frequency)

        if self._session:
            await self._session.close()

    def run(self) -> None:  # pragma: no cover
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_run())


def extract_upwind_detection_datetime(event: dict[str, Any]) -> datetime | None:
    for field_name in ("last_seen_time", "first_seen_time"):
        raw_value = event.get(field_name)
        if not raw_value:
            continue

        try:
            parsed = isoparse(str(raw_value))
            if not isinstance(parsed, datetime):
                continue
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            continue

    return None


def _select_new_events(events: Sequence[dict[str, Any]], cache: Cache) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for event in events:
        key = event.get("id")
        if not key or key in cache:
            continue
        cache[key] = True
        selected.append(event)
    return selected


def filter_new_events(events: Sequence[dict[str, Any]], cache: Cache) -> list[dict[str, Any]]:
    return _select_new_events(events, cache)
