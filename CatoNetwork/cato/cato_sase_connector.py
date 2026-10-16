"""Contains connector, configuration and module."""

import asyncio
import logging
import re
import time
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

from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS

logger = logging.getLogger(__name__)

AUTH_HTTP_CODES = {401, 403}
AUTH_ERROR_MESSAGE = re.compile(
    r"^\s*(permission denied|unauthori[sz]ed|unauthenticated|invalid api key|authentication failed)\b",
    re.IGNORECASE,
)
AUTH_ERROR_CODES = {"UNAUTHENTICATED", "FORBIDDEN"}

# A critical log stops the connector until a user restarts it: only send one for persistent failures
AUTH_FAILURES_BEFORE_CRITICAL = 3
INCOMPLETE_PUSHES_BEFORE_CRITICAL = 5


class IncompletePushError(Exception):
    """The intake did not acknowledge every pushed event."""

    def __init__(self, message: str, marker: str | None) -> None:
        super().__init__(message)
        self.marker = marker


class CatoModuleConfig(BaseModel):
    """Configuration for CatoModule."""

    api_key: str = Field(json_schema_extra={"secret": True})
    account_id: str


class CatoModule(Module):
    """CatoModule."""

    configuration: CatoModuleConfig  # type: ignore[override]


class CatoSaseConnectorConfig(DefaultConnectorConfiguration):
    """CatoSaseConnector configuration."""

    frequency: int = Field(default=60, ge=1)


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

    async def _push_events(self, events: list[EventType]) -> list[str]:
        """
        Push events to intakes.

        Simple wrapper over `self.push_events_to_intakes` to run it async.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return await asyncio.to_thread(
            self.push_events_to_intakes,
            events=events,
            sync=True,
        )

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

    async def next_batch(self) -> int:
        """
        Run one collection cycle: fetch from the saved marker, push, then save the new marker.

        The marker is only saved when the intake acknowledged every event, so a failed push is refetched.
        The authentication failure counter is reset as soon as the fetch succeeds.

        Returns:
            int: the number of events Cato returned (`fetchedCount`)
        """
        processing_start = time.monotonic()

        marker = self.latest_events_feed_id
        feed = await self.cato_client.load_events_feed(marker)
        # A successful fetch proves the credentials work, even if the push below fails.
        # Network and server errors deliberately do not reset this counter: they prove nothing about the credentials.
        self._consecutive_auth_failures = 0
        events = self._serialize_events(feed)

        event_ids = await self._push_events(events) if events else []
        if len(event_ids) != len(events):
            raise IncompletePushError(
                f"The intake acknowledged {len(event_ids)} of {len(events)} events; they will be fetched again",
                marker,
            )

        if feed.marker:
            self._save_events_feed_id(feed.marker)

        logger.debug("Fetched %d events, forwarded %d", feed.fetchedCount, len(event_ids))

        if event_ids:
            intake_key = self.configuration.intake_key
            OUTCOMING_EVENTS.labels(intake_key=intake_key).inc(len(event_ids))
            FORWARD_EVENTS_DURATION.labels(intake_key=intake_key).observe(time.monotonic() - processing_start)

            newest_event_date = _newest_event_date(feed)
            if newest_event_date is not None:
                EVENTS_LAG.labels(intake_key=intake_key).set((datetime.now(UTC) - newest_event_date).total_seconds())

            self.log(f"Forwarded {len(event_ids)} events", level="info")

        return feed.fetchedCount

    async def _sleep(self, seconds: int) -> None:
        """Sleep in 1 second steps, returning early when the connector is stopped."""
        for _ in range(max(0, int(seconds))):
            if not self.running:
                return

            await asyncio.sleep(1)

    async def _backoff(self) -> None:
        """Sleep after an error: exponential delay (2, 4, 8... seconds) capped at `frequency`."""
        self._consecutive_errors += 1
        delay = max(1, min(self.configuration.frequency, 2**self._consecutive_errors))
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
        self._consecutive_errors = 0
        self._consecutive_auth_failures = 0
        self._incomplete_push_marker = None
        self._consecutive_incomplete_pushes = 0

    async def run_cycle(self) -> None:
        """Run `next_batch`, report errors, and sleep when caught up or after an error."""
        try:
            fetched_count = await self.next_batch()

        except IncompletePushError as error:
            self._report_incomplete_push(error)

        except TransportServerError as error:
            if error.code in AUTH_HTTP_CODES:
                self._report_auth_failure(
                    f"Cato API rejected the credentials (HTTP {error.code}): check the API key and its permissions"
                )
            else:
                self.log(f"Cato API server error: {error}", level="error")

        except TransportQueryError as error:
            message = f"Cato API returned an error: {_query_error_message(error)}"
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
        """Collect events until the connector is stopped, then close the HTTP sessions."""
        try:
            while self.running:
                await self.run_cycle()
        finally:
            if self._cato_client is not None:
                await self._cato_client.close()

    def run(self) -> None:
        """Runs Cato Sase."""
        asyncio.run(self.async_run())
