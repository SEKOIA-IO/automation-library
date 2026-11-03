import time
from collections.abc import Iterator
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
            "from": self.cursor.offset if self.cursor.offset else "",
        }

        if not self.cursor.offset:
            start = datetime.now(tz=UTC) - timedelta(hours=self.configuration.initial_hours_lookback)
            payload["filters"] = {"matched_at": {"gte": start.isoformat()}}

        return payload

    def _scroll_events(self) -> Iterator[tuple[dict[str, Any] | None, str | None]]:
        """
        Yield `(event, next_cursor)` for every event of the tenant feed.

        Replaces `FlareApiClient.scroll_events`, which raises on the first event whose details
        are gone (404). Such events are yielded as `None` so the caller can skip them.
        """
        self.limiter.tick()
        for page_resp in self.client.scroll(method="POST", url=self.EVENTS_PAGES_URL, json=self._build_payload()):
            page = page_resp.json()
            for item in page["items"]:
                self.limiter.tick()
                event_resp = self.client.get(url=self.EVENTS_DETAILS_URL, params={"uid": item["metadata"]["uid"]})
                if event_resp.status_code == 404:
                    yield None, page["next"]
                    continue
                event_resp.raise_for_status()
                yield event_resp.json(), page["next"]
            self.limiter.tick()

    @staticmethod
    def _serialize(event: dict[str, Any]) -> str:
        activity = event.get("activity", event)
        data = activity.get("data")
        if isinstance(data, dict):
            # Chat messages embed up to 50 older and 50 newer messages of the conversation as
            # context, which pushes them above the intake's 250kB limit. They are not parsed.
            data.pop("olders", None)
            data.pop("newers", None)
        return orjson.dumps(activity).decode("utf-8")

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
        not_found = 0
        # Number of events of `batch` belonging to fully read pages, and the cursor after them.
        complete, complete_cursor = 0, page_cursor

        try:
            for event, next_cursor in self._scroll_events():
                # Page boundary reached: flush if we already gathered a full batch.
                if next_cursor != page_cursor:
                    if len(batch) >= self.BATCH_SIZE:
                        total += self._push(batch, page_cursor)
                        batch = []
                    complete, complete_cursor = len(batch), page_cursor
                    page_cursor = next_cursor

                if event is None:
                    # Details no longer available on Flare's side: skip the event.
                    not_found += 1
                elif isinstance(event, dict):
                    batch.append(self._serialize(event))
        except Exception:
            # Keep the progress made on fully read pages before failing (e.g. rate limited).
            if complete:
                self._push(batch[:complete], complete_cursor)
            raise

        if batch:
            total += self._push(batch, page_cursor)
        elif not_found and page_cursor:
            # Only unavailable events on the last pages: move past them.
            self.cursor.offset = page_cursor

        intake_key = self.configuration.intake_key

        skipped = f" ({not_found} unavailable events skipped)" if not_found else ""
        if total:
            self.log(f"Forwarded {total} events to the intake{skipped}", level="info")
            EVENTS_LAG.labels(intake_key=intake_key).set(time.time() - batch_start_time)
        else:
            self.log(f"No events to forward{skipped}", level="info")

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
                # Back off before retrying, so a rate-limited API is not hammered again right away.
                time.sleep(self.configuration.frequency)
