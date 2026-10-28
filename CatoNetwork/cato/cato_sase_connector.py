"""Contains connector, configuration and module."""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import aiohttp
import orjson
from dateutil.parser import isoparse
from gql.transport.exceptions import TransportProtocolError, TransportQueryError, TransportServerError
from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration, EventType
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from sekoia_automation.module import Module
from sekoia_automation.storage import PersistentJSON

from client.graphql_client import CatoGraphQLClient
from client.schemas.events_feed import EventsFeedResponseSchema

from .metrics import (
    EVENTS_LAG,
    FETCH_EVENTS_DURATION,
    FORWARD_EVENTS_DURATION,
    OUTCOMING_EVENTS,
    PUSH_EVENTS_DURATION,
)

logger = logging.getLogger(__name__)

AUTH_HTTP_CODES = {401, 403}
AUTH_ERROR_MESSAGE = re.compile(
    r"^\s*(permission denied|unauthori[sz]ed|unauthenticated|invalid api key|authentication failed)\b",
    re.IGNORECASE,
)
AUTH_ERROR_CODES = {"UNAUTHENTICATED", "FORBIDDEN"}

# Cato answers "rate limit for operation: eventsFeed..." when the account exceeds its quota
RATE_LIMIT_ERROR_MESSAGE = re.compile(r"rate limit for operation", re.IGNORECASE)
RATE_LIMIT_HTTP_CODE = 429
RATE_LIMIT_DELAY = 5

# Ceiling of the error backoff, independent of the (short) idle `frequency`: don't hammer Cato during an outage
BACKOFF_MAX_DELAY = 60

# A Cato page (up to 3000 events, ~5 MB) is pushed as several smaller batches sent in parallel:
# one SDK chunk (~9 MB) would be sent as a single slow POST, close to the intake payload limit once escaped.
PUSH_BATCH_MAX_SIZE = 2_000_000
MAX_CONCURRENT_PUSHES = 4

# A critical log stops the connector until a user restarts it: only send one for persistent failures
AUTH_FAILURES_BEFORE_CRITICAL = 3
INCOMPLETE_PUSHES_BEFORE_CRITICAL = 5


class IncompletePushError(Exception):
    """The intake did not acknowledge every pushed event."""

    def __init__(self, message: str, marker: str | None) -> None:
        super().__init__(message)
        self.marker = marker


@dataclass
class PendingPush:
    """A page being pushed to the intake in the background, while the next page is fetched."""

    task: asyncio.Task[tuple[list[str], float]]
    count: int
    marker_before: str | None
    marker_after: str | None
    newest_event_date: datetime | None
    fetch_duration: float


class CatoModuleConfig(BaseModel):
    """Configuration for CatoModule."""

    api_key: str = Field(json_schema_extra={"secret": True})
    account_id: str


class CatoModule(Module):
    """CatoModule."""

    configuration: CatoModuleConfig  # type: ignore[override]


class CatoSaseConnectorConfig(DefaultConnectorConfiguration):
    """CatoSaseConnector configuration."""

    frequency: int = Field(default=5, ge=1)


def _is_auth_query_error(error: TransportQueryError) -> bool:
    """Whether a GraphQL error is an authentication or permission failure (anchored allow-list, no substring)."""
    items: list[Any] = error.errors or [{"message": str(error)}]
    for item in items:
        if not isinstance(item, dict):
            item = {"message": str(item)}

        if AUTH_ERROR_MESSAGE.match(str(item.get("message", ""))):
            return True

        extensions = item.get("extensions")
        if isinstance(extensions, dict) and str(extensions.get("code", "")).upper() in AUTH_ERROR_CODES:
            return True

    return False


def _split_events(events: list[EventType]) -> list[list[EventType]]:
    """Split events into consecutive batches of at most `PUSH_BATCH_MAX_SIZE` characters (at least one event each)."""
    batches: list[list[EventType]] = []
    batch: list[EventType] = []
    size = 0
    for event in events:
        length = len(str(event))
        if batch and size + length > PUSH_BATCH_MAX_SIZE:
            batches.append(batch)
            batch = []
            size = 0

        batch.append(event)
        size += length

    if batch:
        batches.append(batch)

    return batches


def _query_error_message(error: TransportQueryError) -> str:
    """Extract the vendor message of a GraphQL error."""
    if error.errors:
        messages = [str(item.get("message", item)) if isinstance(item, dict) else str(item) for item in error.errors]
        return "; ".join(messages)

    return str(error)


def _newest_event_date(feed: EventsFeedResponseSchema) -> datetime | None:
    """Return the most recent `time` of the records, as an aware datetime, ignoring unparsable values."""
    newest: datetime | None = None
    for account in feed.accounts:
        for record in account.records:
            try:
                event_date = isoparse(record.time)
            except ValueError, OverflowError:
                continue

            if event_date.tzinfo is None:
                event_date = event_date.replace(tzinfo=UTC)

            if newest is None or event_date > newest:
                newest = event_date

    return newest


class CatoSaseConnector(Connector):
    """CatoSaseConnector class to work with cato events."""

    name = "CatoSaseConnector"

    module: CatoModule
    configuration: CatoSaseConnectorConfig

    _cato_client: CatoGraphQLClient | None = None

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        """Init CatoSaseConnector."""

        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._consecutive_errors = 0
        self._consecutive_auth_failures = 0
        self._incomplete_push_marker: str | None = None
        self._consecutive_incomplete_pushes = 0
        self._pending_push: PendingPush | None = None

    @property
    def latest_events_feed_id(self) -> str | None:
        """
        Get last event id.

        More details you can find in the documentation ( look into `eventsFeed Marker` section):
        https://support.catonetworks.com/hc/en-us/articles/360019839477#heading-3

        Returns:
            str | None:
        """
        with self.context as cache:
            result: str | None = cache.get("latest_events_feed_id")

            return result

    def _save_events_feed_id(self, marker: str) -> None:
        with self.context as cache:
            cache["latest_events_feed_id"] = marker

    @property
    def cato_client(self) -> CatoGraphQLClient:
        """
        Get CatoGraphQLClient client.

        Returns:
            CatoGraphQLClient:
        """
        if self._cato_client is not None:
            return self._cato_client

        self._cato_client = CatoGraphQLClient(
            api_key=self.module.configuration.api_key,
            account_id=self.module.configuration.account_id,
        )

        return self._cato_client

    async def _push_events(self, events: list[EventType]) -> tuple[list[str], float]:
        """
        Push events to intakes, as batches of `PUSH_BATCH_MAX_SIZE` characters sent in parallel.

        Args:
            events: list[str]

        Returns:
            tuple[list[str], float]: the acknowledged event ids, in order, and the push duration in seconds
        """
        push_start = time.monotonic()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PUSHES)

        async def push_batch(batch: list[EventType]) -> list[str]:
            # A failed batch acknowledges nothing, once every batch is done: the page is then fetched again,
            # and no batch of this page is still being pushed concurrently with the retry
            try:
                async with semaphore:
                    return await asyncio.to_thread(self.push_events_to_intakes, events=batch, sync=True)
            except Exception as error:
                self.log_exception(error, message=f"Failed to push {len(batch)} Cato SASE events")
                return []

        results = await asyncio.gather(*(push_batch(batch) for batch in _split_events(events)))

        return [event_id for event_ids in results for event_id in event_ids], time.monotonic() - push_start

    def _serialize_events(self, feed: EventsFeedResponseSchema) -> list[EventType]:
        events: list[EventType] = []
        discarded = 0
        for account in feed.accounts:
            for record in account.records:
                event = orjson.dumps({"event_time": record.time, **record.fieldsMap}).decode("utf-8")

                # The SDK silently drops oversized events: drop them here so the push can be fully acknowledged.
                # Characters, not bytes, on purpose: this mirrors the SDK's own check in `_chunk_events`
                # (`len(result_event) > EVENT_BYTES_MAX_SIZE` on the serialized string). Counting bytes would drop
                # multi-byte events the SDK and the intake accept; a persistent intake rejection is already
                # reported by the incomplete-push critical.
                if len(event) > EVENT_BYTES_MAX_SIZE:
                    discarded += 1
                    continue

                events.append(event)

        if discarded > 0:
            self.put_discarded_events(intake_key=self.configuration.intake_key, count=discarded)
            self.log(f"Discarded {discarded} events longer than {EVENT_BYTES_MAX_SIZE} characters", level="warning")

        return events

    async def _complete_pending_push(self) -> None:
        """
        Wait for the page being pushed, then save its marker if the intake acknowledged every event.

        Raises:
            IncompletePushError: the intake did not acknowledge every event; the marker is not advanced
        """
        pending, self._pending_push = self._pending_push, None
        if pending is None:
            return

        event_ids, push_duration = await pending.task
        if len(event_ids) != pending.count:
            raise IncompletePushError(
                f"The intake acknowledged {len(event_ids)} of {pending.count} events; they will be fetched again",
                pending.marker_before,
            )

        self._incomplete_push_marker = None
        self._consecutive_incomplete_pushes = 0
        if pending.marker_after:
            self._save_events_feed_id(pending.marker_after)

        intake_key = self.configuration.intake_key
        OUTCOMING_EVENTS.labels(intake_key=intake_key).inc(len(event_ids))
        FETCH_EVENTS_DURATION.labels(intake_key=intake_key).observe(pending.fetch_duration)
        PUSH_EVENTS_DURATION.labels(intake_key=intake_key).observe(push_duration)
        FORWARD_EVENTS_DURATION.labels(intake_key=intake_key).observe(pending.fetch_duration + push_duration)
        if pending.newest_event_date is not None:
            EVENTS_LAG.labels(intake_key=intake_key).set(
                (datetime.now(UTC) - pending.newest_event_date).total_seconds()
            )

        self.log(
            f"Forwarded {len(event_ids)} events (fetch {pending.fetch_duration:.1f}s, push {push_duration:.1f}s)",
            level="info",
        )

    async def _drain_pending_push(self) -> None:
        """Complete the page being pushed when the connector stops, reporting failures instead of raising."""
        try:
            await self._complete_pending_push()
        except IncompletePushError as error:
            self.log(str(error), level="error")
        except Exception as error:
            self.log_exception(error, message="Failed to forward the last Cato SASE events")

    async def next_batch(self) -> int:
        """
        Run one collection cycle: fetch the next page while the previous one is pushed, then push the new page.

        The next page is fetched from the marker of the page being pushed, so fetches and pushes overlap.
        A marker is only saved once the intake acknowledged every event of its page: when a push fails,
        the prefetched page is dropped and the next cycle fetches again from the saved marker.
        The authentication failure counter is reset as soon as the fetch succeeds.

        Returns:
            int: the number of events Cato returned (`fetchedCount`)
        """
        # Save the marker of a finished push now: when Cato keeps failing, it would otherwise wait for the next fetch
        if self._pending_push is not None and self._pending_push.task.done():
            await self._complete_pending_push()

        fetch_start = time.monotonic()
        marker = self._pending_push.marker_after if self._pending_push else self.latest_events_feed_id
        feed = await self.cato_client.load_events_feed(marker)
        fetch_duration = time.monotonic() - fetch_start
        # A successful fetch proves the credentials work, even if the push below fails.
        # Network and server errors deliberately do not reset this counter: they prove nothing about the credentials.
        self._consecutive_auth_failures = 0
        events = self._serialize_events(feed)

        await self._complete_pending_push()

        logger.debug("Fetched %d events in %.1fs", feed.fetchedCount, fetch_duration)

        if events:
            self._pending_push = PendingPush(
                task=asyncio.create_task(self._push_events(events)),
                count=len(events),
                marker_before=marker,
                marker_after=feed.marker or marker,
                newest_event_date=_newest_event_date(feed),
                fetch_duration=fetch_duration,
            )
        elif feed.marker:
            self._save_events_feed_id(feed.marker)

        return feed.fetchedCount

    async def _sleep(self, seconds: int) -> None:
        """Sleep in 1 second steps, returning early when the connector is stopped."""
        for _ in range(max(0, int(seconds))):
            if not self.running:
                return

            await asyncio.sleep(1)

    async def _backoff(self) -> None:
        """Sleep after an error: exponential delay (2, 4, 8... seconds) capped at `frequency`, at least 60 seconds."""
        self._consecutive_errors += 1
        max_delay = max(self.configuration.frequency, BACKOFF_MAX_DELAY)
        delay = max(1, min(max_delay, 2**self._consecutive_errors))
        await self._sleep(delay)

    def _report_auth_failure(self, message: str) -> None:
        """Log an auth failure as `error`, and as `critical` once it has repeated enough times in a row."""
        self._consecutive_auth_failures += 1
        level: Literal["critical", "error"] = (
            "critical" if self._consecutive_auth_failures >= AUTH_FAILURES_BEFORE_CRITICAL else "error"
        )
        self.log(message, level=level)

    def _report_incomplete_push(self, error: IncompletePushError) -> None:
        """Log an incomplete push; once it keeps failing from the same marker, send a single critical log."""
        if error.marker != self._incomplete_push_marker:
            self._incomplete_push_marker = error.marker
            self._consecutive_incomplete_pushes = 0

        self._consecutive_incomplete_pushes += 1
        if self._consecutive_incomplete_pushes == INCOMPLETE_PUSHES_BEFORE_CRITICAL:
            self.log(
                f"The intake keeps rejecting events from marker {error.marker} "
                f"({self._consecutive_incomplete_pushes} attempts in a row): the marker is not advanced, "
                "so no event is lost, but the collection is blocked",
                level="critical",
            )
        else:
            self.log(str(error), level="error")

    def _reset_failure_counters(self) -> None:
        # The incomplete push counter is reset by `_complete_pending_push` only: a cycle that merely starts a push
        # succeeds even when that push will be rejected. Keep the backoff growing while pushes keep being rejected.
        if self._consecutive_incomplete_pushes == 0:
            self._consecutive_errors = 0
        self._consecutive_auth_failures = 0

    async def _wait_rate_limit(self) -> None:
        """Expected under heavy load: retry shortly, without the exponential backoff of real errors."""
        self.log(f"Cato API rate limit reached, retrying in {RATE_LIMIT_DELAY} seconds", level="warning")
        await self._sleep(RATE_LIMIT_DELAY)

    async def run_cycle(self) -> None:
        """Run `next_batch`, report errors, and sleep when caught up or after an error."""
        try:
            fetched_count = await self.next_batch()

        except IncompletePushError as error:
            self._report_incomplete_push(error)

        except TransportServerError as error:
            if error.code == RATE_LIMIT_HTTP_CODE:
                await self._wait_rate_limit()
                return

            if error.code in AUTH_HTTP_CODES:
                self._report_auth_failure(
                    f"Cato API rejected the credentials (HTTP {error.code}): check the API key and its permissions"
                )
            else:
                self.log(f"Cato API server error: {error}", level="error")

        except TransportQueryError as error:
            message = f"Cato API returned an error: {_query_error_message(error)}"
            if RATE_LIMIT_ERROR_MESSAGE.search(message):
                await self._wait_rate_limit()
                return

            if _is_auth_query_error(error):
                self._report_auth_failure(message)
            else:
                self.log(message, level="error")

        except (TransportProtocolError, aiohttp.ClientError, TimeoutError) as error:
            self.log(f"Failed to query the Cato API: {error!r}", level="error")

        except Exception as error:
            self.log_exception(error, message="Unexpected error while collecting Cato SASE events")

        else:
            self._reset_failure_counters()
            if fetched_count == 0:
                await self._sleep(self.configuration.frequency)

            return

        await self._backoff()

    async def async_run(self) -> None:
        """Collect events until the connector is stopped, finish the last push, then close the HTTP sessions."""
        try:
            while self.running:
                await self.run_cycle()
        finally:
            await self._drain_pending_push()
            if self._cato_client is not None:
                await self._cato_client.close()

    def run(self) -> None:
        """Runs Cato Sase."""
        asyncio.run(self.async_run())
