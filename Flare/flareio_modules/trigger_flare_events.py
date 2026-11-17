import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any, NamedTuple

import orjson
import requests
from flareio import FlareApiClient
from flareio.ratelimit import Limiter
from requests.adapters import HTTPAdapter
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from urllib3.util import Retry

from flareio_modules import FlareIOModule
from flareio_modules.metrics import (
    DISCARDED_EVENTS,
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    OUTCOMING_EVENTS,
    TRUNCATED_EVENTS,
)

# Added to `data`: the fields that were cut to fit the intake size limit, e.g. ["extracted_content", "files"]
TRUNCATED_FIELDS = "truncated_fields"
# `features` lists the parser reads in full; of the other lists, it only reads the first item
FULLY_PARSED_FEATURES = frozenset({"emails", "usernames"})


class SerializedEvent(NamedTuple):
    text: str
    # In UTF-8 bytes, as the intake measures it
    size: int
    truncated_fields: list[str]


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
        return FlareApiClient(
            api_key=self.module.configuration.api_key,
            tenant_id=self.module.configuration.tenant_id,
            session=self._create_session(),
        )

    @staticmethod
    def _create_session() -> requests.Session:
        """
        The SDK's session retries 429, 502, 503 and 504 only, while Flare also answers intermittent 500s to both the
        search and the details: without a retry, each one fails the batch and costs a `frequency` wait in `run()`.
        Same retries as the SDK's otherwise.
        """
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=2,
            backoff_max=15,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET", "POST"},
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

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

    def _fetch_details(self, item_metadata: dict[str, Any]) -> dict[str, Any] | None:
        self.limiter.tick()
        event_resp = self.client.get(url=self.EVENTS_DETAILS_URL, params={"uid": item_metadata["uid"]})
        if event_resp.status_code == 404:
            return None
        event_resp.raise_for_status()
        event = event_resp.json()
        # The date Flare matched the item to the tenant is only in the search results; the parser uses it as the
        # event's date, since the item can be years old (e.g. the history Flare matches when a tenant is created)
        activity = event.get("activity", event)
        activity["metadata"] = {**(activity.get("metadata") or {}), "matched_at": item_metadata.get("matched_at")}
        return event

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
                items_metadata = [item["metadata"] for item in page["items"]]
                # `map` returns the results in the order of the items, whatever the order the calls complete in
                for event in details_executor.map(self._fetch_details, items_metadata):
                    yield event, page["next"]
        finally:
            # On an error, don't wait for the calls still running (the prefetched page, the page's other
            # details): the error reaches `run()` at once. Their results are not used.
            page_executor.shutdown(wait=False, cancel_futures=True)
            details_executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _serialize(event: dict[str, Any]) -> SerializedEvent:
        activity = event.get("activity", event)
        data = activity.get("data")
        if isinstance(data, dict):
            # Chat messages embed up to 50 older and 50 newer messages of the conversation as
            # context, which pushes them above the intake's 250kB limit. They are not parsed.
            data.pop("olders", None)
            data.pop("newers", None)
        serialized = orjson.dumps(activity)
        # Measured in UTF-8 bytes: at least the number of characters the SDK counts, and what the intake receives
        truncated_fields: list[str] = []
        if len(serialized) > EVENT_BYTES_MAX_SIZE and isinstance(data, dict):
            serialized = FlareEventsConnector._cut_oversized_fields(activity, data, serialized)
            truncated_fields = data.get(TRUNCATED_FIELDS, [])
        return SerializedEvent(serialized.decode("utf-8"), len(serialized), truncated_fields)

    @staticmethod
    def _oversized_fields(data: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], str, int]]:
        """
        Yield `(name, parent, key, items_to_keep)` for the fields that may be cut, least useful first:
        - `extracted_content`, the text of an attachment, which the parser does not read;
        - the lists of `features` the parser only reads the first item of (IP addresses, domains, URLs…);
        - `content`, copied as-is into `flare.events.<type>.content`: analysts see its beginning;
        - `files`, the file list of stealer logs and ransomware leaks;
        - `credentials` of stealer logs (`header.credential_count` keeps their number);
        - the `features` lists the parser reads in full (emails, usernames), e.g. leaks of thousands of emails.
        """
        yield "extracted_content", data, "extracted_content", 0
        features = data.get("features")
        if not isinstance(features, dict):
            features = {}
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
            if key in FULLY_PARSED_FEATURES:
                yield f"features.{key}", features, key, 0

    @staticmethod
    def _cut_oversized_fields(activity: dict[str, Any], data: dict[str, Any], serialized: bytes) -> bytes:
        """
        Cut the end of the event's biggest fields until it fits the intake size limit, which otherwise discards
        the whole event: attachments, blog posts, source code or stealer logs can carry several hundred kB.
        The names of the cut fields are listed in `data.truncated_fields`.
        """
        truncated: list[str] = []
        for name, parent, key, keep in FlareEventsConnector._oversized_fields(data):
            if len(serialized) <= EVENT_BYTES_MAX_SIZE:
                break
            value = parent.get(key)
            if not isinstance(value, (str, list)) or len(value) <= keep:
                continue

            truncated.append(name)
            data[TRUNCATED_FIELDS] = truncated
            # Measured with the field's name listed, so that the list itself fits too
            excess = len(orjson.dumps(activity)) - EVENT_BYTES_MAX_SIZE
            prefix = FlareEventsConnector._longest_prefix(value, len(orjson.dumps(value)) - excess)
            parent[key] = value[: max(keep, prefix)]
            serialized = orjson.dumps(activity)
        return serialized

    @staticmethod
    def _longest_prefix(value: str | list[Any], max_size: int) -> int:
        """
        Length of the longest prefix of `value` whose serialized form (quotes and escapes, or brackets and commas)
        fits `max_size`. Every character or item takes at least one byte, so no prefix longer than `max_size` fits.
        """
        low, high = 0, min(len(value), max_size)
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

    def _report_oversized(self, event: dict[str, Any], serialized: SerializedEvent) -> None:
        if not serialized.truncated_fields and serialized.size <= EVENT_BYTES_MAX_SIZE:
            return

        header = event.get("activity", event).get("header") or {}
        description = f"{header.get('type')} event {header.get('uid')}"
        intake_key = self.configuration.intake_key
        if serialized.truncated_fields:
            TRUNCATED_EVENTS.labels(intake_key=intake_key).inc()
            fields = ", ".join(serialized.truncated_fields)
            self.log(f"Cut the fields {fields} of the {description} to fit the intake size limit", level="info")
        if serialized.size > EVENT_BYTES_MAX_SIZE:
            DISCARDED_EVENTS.labels(intake_key=intake_key).inc()
            self.log(
                f"The {description} is still above the intake size limit ({serialized.size} bytes) "
                "and will be discarded",
                level="warning",
            )

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
                    serialized = self._serialize(event)
                    self._report_oversized(event, serialized)
                    batch.append(serialized.text)
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
