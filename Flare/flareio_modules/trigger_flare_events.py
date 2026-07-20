import time
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
from flareio import FlareApiClient
from flareio.ratelimit import Limiter
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from flareio_modules import FlareIOModule
from flareio_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS


class FlareEventsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    page_size: int = 10
    initial_hours_lookback: int = 1
    throttle_seconds: float = 0.25


class FlareEventsConnector(Connector):
    module: FlareIOModule
    configuration: FlareEventsConnectorConfiguration

    EVENTS_PAGES_URL = "/firework/v4/events/tenant/_search"
    EVENTS_DETAILS_URL = "/firework/v2/activities/"
    MAX_PAGE_SIZE = 10
    BATCH_SIZE = 100

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cursor = CheckpointCursor(path=self.data_path)

    @cached_property
    def client(self) -> FlareApiClient:
        # The SDK builds its own session with retries on 429/502/503/504, scoped to the tenant.
        return FlareApiClient(
            api_key=self.module.configuration.api_key,
            tenant_id=self.module.configuration.tenant_id,
        )

    @cached_property
    def limiter(self) -> Limiter:
        return Limiter.from_seconds(self.configuration.throttle_seconds)

    def _build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "size": min(self.configuration.page_size, self.MAX_PAGE_SIZE),
            "order": "asc",
            "from": self.cursor.offset if self.cursor.offset else ""
        }

        if not self.cursor.offset:
            start = datetime.now(tz=UTC) - timedelta(hours=self.configuration.initial_hours_lookback)
            payload["filters"] = {"estimated_created_at": {"gte": start.isoformat()}}

        return payload

    def _push(self, events: list[str], cursor: str | None) -> int:
        self.push_events_to_intakes(events=events)
        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events))
        if cursor:
            self.cursor.offset = cursor
        return len(events)

    def next_batch(self) -> None:
        batch_start_time = time.time()

        batch: list[str] = []
        # Cursor of the page currently accumulated in `batch`. Every event of a page shares
        # the same `next`, so the checkpoint is only committed on page boundaries to avoid
        # skipping events that were not yet forwarded when resuming.
        page_cursor = self.cursor.offset
        total = 0

        for result in self.client.scroll_events(
            method="POST",
            pages_url=self.EVENTS_PAGES_URL,
            events_url=self.EVENTS_DETAILS_URL,
            json=self._build_payload(),
            _pages_limiter=self.limiter,
            _events_limiter=self.limiter,
        ):
            # Page boundary reached: flush if we already gathered a full batch.
            if result.next != page_cursor:
                if len(batch) >= self.BATCH_SIZE:
                    total += self._push(batch, page_cursor)
                    batch = []
                page_cursor = result.next

            event = result.event
            if isinstance(event, dict):
                batch.append(orjson.dumps(event.get("activity", event)).decode("utf-8"))

        if batch:
            total += self._push(batch, page_cursor)

        intake_key = self.configuration.intake_key

        if total:
            self.log(f"Forwarded {total} events to the intake", level="info")
            EVENTS_LAG.labels(intake_key=intake_key).set(time.time() - batch_start_time)
        else:
            self.log("No events to forward", level="info")

        batch_duration = time.time() - batch_start_time
        FORWARD_EVENTS_DURATION.labels(intake_key=intake_key).observe(batch_duration)

        delta_sleep = self.configuration.frequency - int(batch_duration)
        if delta_sleep > 0:
            time.sleep(delta_sleep)

    def run(self) -> None:  # pragma: no cover
        self.log(message="Start fetching Flare events", level="info")

        while self.running:
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
