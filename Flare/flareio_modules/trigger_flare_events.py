import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any

import orjson
import requests
from flareio import FlareApiClient
from flareio.ratelimit import Limiter
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE

from flareio_modules import FlareIOModule
from flareio_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

# Added to `data`: the fields that were cut to fit the intake size limit, e.g. ["extracted_content", "files"]
TRUNCATED_FIELDS = "truncated_fields"
# `features` lists the parser reads in full; of the other lists, it only reads the first item
FULLY_PARSED_FEATURES = frozenset({"emails", "usernames"})


class FlareEventsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60
    page_size: int = 10
    initial_hours_lookback: int = 1
    throttle_seconds: float = 0.25
    concurrency: int = 4


class ThreadSafeLimiter:
    """`flareio`'s `Limiter`, shared by the threads that call Flare: one call starts every `throttle_seconds`."""

    def __init__(self, limiter: Limiter) -> None:
        self._limiter = limiter
        self._lock = threading.Lock()

    def tick(self) -> None:
        with self._lock:
            self._limiter.tick()


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
    def limiter(self) -> ThreadSafeLimiter:
        return ThreadSafeLimiter(Limiter.from_seconds(self.configuration.throttle_seconds))

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

    def _next_page(self, pages: Iterator[requests.Response]) -> requests.Response | None:
        self.limiter.tick()
        return next(pages, None)

    def _fetch_details(self, uid: str) -> dict[str, Any] | None:
        self.limiter.tick()
        event_resp = self.client.get(url=self.EVENTS_DETAILS_URL, params={"uid": uid})
        if event_resp.status_code == 404:
            return None
        event_resp.raise_for_status()
        return event_resp.json()

    def _scroll_events(self) -> Iterator[tuple[dict[str, Any] | None, str | None]]:
        """
        Yield `(event, next_cursor)` for every event of the tenant feed, in the feed's order.

        Replaces `FlareApiClient.scroll_events`, which raises on the first event whose details
        are gone (404). Such events are yielded as `None` so the caller can skip them.

        The search only returns the events' metadata, so each event needs its own details call. These calls
        run `concurrency` at a time, and the next page is read meanwhile; the limiter still paces every call.
        """
        pages = iter(self.client.scroll(method="POST", url=self.EVENTS_PAGES_URL, json=self._build_payload()))
        page_executor = ThreadPoolExecutor(max_workers=1)
        details_executor = ThreadPoolExecutor(max_workers=max(1, self.configuration.concurrency))
        try:
            next_page = page_executor.submit(self._next_page, pages)
            while (page_resp := next_page.result()) is not None:
                page = page_resp.json()
                next_page = page_executor.submit(self._next_page, pages)
                uids = [item["metadata"]["uid"] for item in page["items"]]
                # `map` returns the results in the order of `uids`, whatever the order the calls complete in
                for event in details_executor.map(self._fetch_details, uids):
                    yield event, page["next"]
        finally:
            # On an error, don't wait for the calls still running (the prefetched page, the page's other
            # details): the error reaches `run()` at once. Their results are not used.
            page_executor.shutdown(wait=False, cancel_futures=True)
            details_executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _serialize(event: dict[str, Any]) -> str:
        activity = event.get("activity", event)
        data = activity.get("data")
        if isinstance(data, dict):
            # Chat messages embed up to 50 older and 50 newer messages of the conversation as
            # context, which pushes them above the intake's 250kB limit. They are not parsed.
            data.pop("olders", None)
            data.pop("newers", None)
        serialized = orjson.dumps(activity)
        # Measured in UTF-8 bytes: at least the number of characters the SDK counts, and what the intake receives
        if len(serialized) > EVENT_BYTES_MAX_SIZE and isinstance(data, dict):
            serialized = FlareEventsConnector._cut_oversized_fields(activity, data)
        return serialized.decode("utf-8")

    @staticmethod
    def _oversized_fields(data: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], str, int]]:
        """
        Yield `(name, parent, key, items_to_keep)` for the fields that may be cut, least useful first:
        - `extracted_content`, the text of an attachment, which the parser does not read;
        - the lists of `features` the parser only reads the first item of (IP addresses, domains, URLs…);
        - `content`, kept as raw text;
        - `files`, the file list of stealer logs and ransomware leaks;
        - `credentials` of stealer logs (`header.credential_count` keeps their number);
        - the `features` lists the parser reads in full (emails, usernames), e.g. leaks of thousands of emails.
        """
        yield "extracted_content", data, "extracted_content", 0
        features = data.get("features")
        lists: list[str] = []
        if isinstance(features, dict):
            lists = sorted(
                (key for key, value in features.items() if isinstance(value, list)),
                key=lambda key: len(orjson.dumps(features[key])),
                reverse=True,
            )
            for key in lists:
                if key not in FULLY_PARSED_FEATURES:
                    yield f"features.{key}", features, key, 1
        yield "content", data, "content", 0
        yield "files", data, "files", 0
        yield "credentials", data, "credentials", 0
        for key in lists:
            if key in FULLY_PARSED_FEATURES and isinstance(features, dict):
                yield f"features.{key}", features, key, 0

    @staticmethod
    def _cut_oversized_fields(activity: dict[str, Any], data: dict[str, Any]) -> bytes:
        """
        Cut the end of the event's biggest fields until it fits the intake size limit, which otherwise discards
        the whole event: attachments, blog posts, source code or stealer logs can carry several hundred kB.
        The names of the cut fields are listed in `data.truncated_fields`.
        """
        truncated: list[str] = []
        serialized = orjson.dumps(activity)
        for name, parent, key, keep in FlareEventsConnector._oversized_fields(data):
            if len(serialized) <= EVENT_BYTES_MAX_SIZE:
                break
            value = parent.get(key)
            if not (isinstance(value, str) and value) and not (isinstance(value, list) and len(value) > keep):
                continue

            truncated.append(name)
            data[TRUNCATED_FIELDS] = truncated
            # Measured with the field's name listed, so that the list itself fits too
            excess = len(orjson.dumps(activity)) - EVENT_BYTES_MAX_SIZE
            if isinstance(value, str):
                parent[key] = value[: FlareEventsConnector._longest_prefix(value, len(orjson.dumps(value)) - excess)]
            else:
                end, removed = len(value), 0
                while end > keep and removed < excess:
                    end -= 1
                    # The item, and the comma before it unless it is the first one
                    removed += len(orjson.dumps(value[end])) + (end > 0)
                parent[key] = value[:end]
            serialized = orjson.dumps(activity)
        return serialized

    @staticmethod
    def _longest_prefix(value: str, max_size: int) -> int:
        """Length of the longest prefix of `value` whose serialized form (quotes, escapes) fits `max_size`."""
        low, high = 0, len(value)
        while low < high:
            middle = (low + high + 1) // 2
            if len(orjson.dumps(value[:middle])) <= max_size:
                low = middle
            else:
                high = middle - 1
        return low

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
