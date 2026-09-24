import time
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cached_property
from threading import Lock
from typing import Any

import orjson
from pydantic import Field
from sekoia_automation.checkpoint import CheckpointTimestamp, TimeUnit
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from sekoia_automation.storage import PersistentJSON

from slack_modules import SlackAuditLogsModule
from slack_modules.client import AuditLogsClient
from slack_modules.errors import AuthenticationError, PlanError, SlackAuditLogsError

Batch = tuple[list[str], datetime | None]


class SlackAuditLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Seconds to wait between two collections of new events",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=9999,
        description="Maximum number of events fetched per request to Slack (Slack caps this at 9999)",
    )
    ratelimit_per_minute: int = Field(
        default=30,
        ge=1,
        le=50,
        description=(
            "Maximum requests sent to Slack per minute. Slack allows 50 for the whole organization, "
            "shared with your other Slack apps"
        ),
    )
    timebuffer: int = Field(
        default=60,
        ge=1,
        le=3600,
        description=(
            "Seconds to wait before collecting a new event, so that events Slack publishes with a delay are not missed"
        ),
    )
    lookback_seconds: int = Field(
        default=3600,
        ge=60,
        description=(
            "How far back in time the very first collection goes, in seconds. Ignored once the "
            "connector has collected at least once"
        ),
    )
    excluded_actions: list[str] = Field(
        default=[],
        description=(
            "Slack actions to drop instead of forwarding, for example file_downloaded. Leave empty "
            "to collect everything. An action added here stops being collected from now on and "
            "cannot be recovered later without re-collecting the whole period"
        ),
    )


@dataclass
class WindowProgress:
    """What earlier cycles left behind for the window starting at a given second."""

    # Frozen at the window's opening so a resumed window is read to the same bound.
    window_end: int | None = None
    cursor: str = ""
    pushed_ids: list[str] = field(default_factory=list)
    truncated: bool = False
    drained: bool = False


class SlackAuditLogsConnector(Connector):
    """Forwards Slack Enterprise Grid audit events to a Sekoia intake."""

    name = "Slack Audit Logs"
    description = "Collect audit events from the Slack Audit Logs API"

    module: SlackAuditLogsModule
    configuration: SlackAuditLogsConnectorConfiguration

    # Slack pages newest first, so the backlog is read as bounded windows walked forward.
    SUB_WINDOW_SECONDS = 3600
    LEDGER_PAGES = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Written from the SDK's worker threads, read once they have finished.
        self._chunk_lock = Lock()
        self._failed_chunks = 0

    @property
    def frequency(self) -> int:
        return self.configuration.frequency

    @cached_property
    def client(self) -> AuditLogsClient:
        return AuditLogsClient(
            base_url=self.module.configuration.base_url,
            token=self.module.configuration.token,
            per_minute=self.configuration.ratelimit_per_minute,
        )

    @cached_property
    def checkpoint(self) -> CheckpointTimestamp:
        return CheckpointTimestamp(
            path=self._data_path,
            time_unit=TimeUnit.SECOND,
            start_at=timedelta(seconds=self.configuration.lookback_seconds),
            # The SDK default clamps past 30 days, silently skipping what a longer outage spans.
            ignore_older_than=None,
        )

    @cached_property
    def pending(self) -> PersistentJSON:
        # Its own file: PersistentJSON rewrites the whole of it, and would clobber the checkpoint.
        return PersistentJSON("pending.json", self._data_path)

    def next_run(self) -> None:
        # The SDK skips its pause after any cycle that forwarded, which would poll an active org flat out.
        started = time.time()
        super().next_run()

        remaining = self.frequency - (time.time() - started)
        if remaining > 0:
            time.sleep(remaining)

    def _send_chunk(
        self, batch_api: str, chunk_index: int, chunk: list[Any], collect_ids: dict[int, list[str]]
    ) -> None:
        # In a `finally`: super()'s failure handler logs over HTTP, which re-raises in the same outage.
        try:
            super()._send_chunk(batch_api, chunk_index, chunk, collect_ids)
        finally:
            # The SDK inserts the key only once the POST succeeded.
            if chunk_index not in collect_ids:
                with self._chunk_lock:
                    self._failed_chunks += 1

    def push_events_to_intakes(self, events: list[str], sync: bool = False) -> list[str]:
        """Forward a batch, and refuse to let a forward that did not happen pass for one that did.

        The SDK returns only the ids that landed and next_run() discards even that, so a partly
        delivered batch looks like a complete one. Raising keeps the window uncommitted.
        """
        self._failed_chunks = 0

        pushed = super().push_events_to_intakes(events, sync)

        if self._failed_chunks:
            self.log(
                message=(
                    f"{self._failed_chunks} of this batch's chunks did not reach the intake. Nothing is "
                    "recorded and the window stays uncommitted, so this page is read again next cycle "
                    "from the cursor in pending.json."
                ),
                level="warning",
            )

            raise SlackAuditLogsError(
                f"{self._failed_chunks} of this batch's chunks did not reach the intake "
                f"({len(events)} events were being forwarded)"
            )

        return pushed

    def _resume(self, window_start: int) -> WindowProgress:
        """What is stored for the window starting at `window_start`, or a blank slate for a new one."""
        with self.pending as cache:
            if cache.get("window_start") != window_start:
                return WindowProgress()

            return WindowProgress(
                window_end=cache.get("window_end"),
                cursor=cache.get("cursor") or "",
                pushed_ids=list(cache.get("pushed_ids") or []),
                truncated=bool(cache.get("truncated")),
            )

    def _remember(self, window_start: int, window_end: int, cursor: str, progress: WindowProgress) -> None:
        # Updated with the file: _drain compares against it to spot a rejected opening cursor.
        progress.cursor = cursor

        with self.pending as cache:
            cache["window_start"] = window_start
            cache["window_end"] = window_end
            cache["cursor"] = cursor
            cache["pushed_ids"] = list(progress.pushed_ids)
            cache["truncated"] = progress.truncated

    def _forget(self) -> None:
        # Emptied rather than cleared: PersistentJSON re-reads the file whenever its cache is falsy.
        with self.pending as cache:
            cache["window_start"] = None
            cache["window_end"] = None
            cache["cursor"] = ""
            cache["pushed_ids"] = []
            cache["truncated"] = False

    def _trim(self, progress: WindowProgress) -> None:
        """Keep only the newest ids: unbounded, the ledger would be rewritten whole after every page."""
        bound = self.LEDGER_PAGES * self.configuration.limit

        if len(progress.pushed_ids) > bound:
            # A re-read restarts at page 1, so keep the ids appended first.
            progress.pushed_ids = progress.pushed_ids[:bound]
            progress.truncated = True

    def iterate(self) -> Generator[Batch, None, None]:
        try:
            settled_until = int(datetime.now(UTC).timestamp()) - self.configuration.timebuffer
            # Slack's `oldest` is inclusive: +1 means an event is never delivered twice.
            oldest = self.checkpoint.offset + 1

            while oldest <= settled_until:
                progress = self._resume(oldest)

                if progress.window_end is not None and progress.window_end > settled_until:
                    self.log(
                        message=(
                            f"The window in flight ends at {progress.window_end}, after the settled "
                            f"boundary {settled_until}: the clock has most likely stepped backwards. "
                            "Waiting for it to catch up."
                        ),
                        level="warning",
                    )
                    return

                latest = (
                    progress.window_end
                    if progress.window_end is not None
                    else min(oldest + self.SUB_WINDOW_SECONDS - 1, settled_until)
                )

                yield from self._drain(oldest, latest, progress)

                if not progress.drained:
                    # Page budget spent. Not committing is what lets the next cycle carry on here.
                    return

                self.checkpoint.offset = latest
                self._forget()

                oldest = latest + 1
        except (AuthenticationError, PlanError) as error:
            self.log(
                message=(
                    f"Slack refused the collection: {error}. Check that the token carries "
                    "auditlogs:read, that the app is installed on the Enterprise organization "
                    "(not a workspace), and that the organization is on Enterprise Grid."
                ),
                level="critical",
            )
        except OSError as error:
            self.log(
                message=(
                    f"Cannot read or record the collection state under {self._data_path} ({error}). "
                    "Events already forwarded will be sent again on every cycle until that path is "
                    "writable - fix the volume mount before the intake fills up."
                ),
                level="critical",
            )
            raise

    def _drain(self, oldest: int, latest: int, progress: WindowProgress) -> Generator[Batch, None, None]:
        """Read one window, carrying on from any stored cursor."""
        attempted = progress.cursor

        try:
            yield from self._read(oldest, latest, attempted, progress)
        except (AuthenticationError, PlanError):
            raise
        except SlackAuditLogsError as error:
            # Past the opening cursor the fault lies elsewhere, and a re-read would re-deliver.
            if not attempted or progress.cursor != attempted:
                raise

            # Cleared before the re-read so a second failure does not offer it again.
            self.log(
                message=f"Slack rejected the stored cursor ({error}); re-reading the window from its start.",
                level="warning",
            )
            if progress.truncated:
                self.log(
                    message=(
                        "This window's ledger had been trimmed, so this re-read may deliver its "
                        "earliest events to the intake a second time."
                    ),
                    level="warning",
                )

            self._remember(oldest, latest, "", progress)
            yield from self._read(oldest, latest, "", progress)

    def _read(self, oldest: int, latest: int, cursor: str, progress: WindowProgress) -> Generator[Batch, None, None]:
        """Walk the window's pages from `cursor`, forwarding each one."""
        excluded = set(self.configuration.excluded_actions)

        for entries, next_cursor in self.client.iter_pages(
            oldest=oldest, latest=latest, limit=self.configuration.limit, cursor=cursor
        ):
            # Grown as entries are accepted: a snapshot would let a repeated id through twice.
            seen = set(progress.pushed_ids)
            fresh = []
            for event in entries:
                identifier = self._identifier(event)
                if identifier is not None:
                    if identifier in seen:
                        continue
                    seen.add(identifier)
                if event.get("action") not in excluded:
                    fresh.append(event)

            if fresh:
                serialised = [orjson.dumps(event).decode("utf-8") for event in fresh]

                self._warn_about_missing_ids(fresh)
                self._report_oversized(fresh, serialised)

                yield serialised, self._newest_date(fresh)

                # Reached only once the SDK pushed, so nothing is recorded ahead of what was sent.
                progress.pushed_ids.extend(
                    identifier for event in fresh if (identifier := self._identifier(event)) is not None
                )
                self._trim(progress)

            self._remember(oldest, latest, next_cursor, progress)

            if not next_cursor:
                progress.drained = True
                return

    def _report_oversized(self, entries: list[dict[str, Any]], serialised: list[str]) -> None:
        """Name the events the platform will discard for their size, because nothing else will.

        The SDK drops them before a chunk exists, so no failure is countable and holding the window
        back would stall it forever. Naming them is the only honest handling left.
        """
        oversized = [
            (self._identifier(entry) or "<no id>", len(payload))
            for entry, payload in zip(entries, serialised)
            if len(payload) > EVENT_BYTES_MAX_SIZE
        ]
        if not oversized:
            return

        self.log(
            message=(
                f"{len(oversized)} audit event(s) exceed the platform's per-event limit of "
                f"{EVENT_BYTES_MAX_SIZE} bytes and are discarded before any request is made, so they "
                "will never reach the intake and cannot be recovered by a retry: "
                + ", ".join(f"id {identifier} ({size} bytes)" for identifier, size in oversized)
            ),
            level="critical",
        )

    def _warn_about_missing_ids(self, entries: list[dict[str, Any]]) -> None:
        without_id = sum(1 for entry in entries if self._identifier(entry) is None)
        if not without_id:
            return

        self.log(
            message=(
                f"Forwarded {without_id} of {len(entries)} entries with no id. Nothing can hold those "
                "back, so a re-read of this window may deliver them to the intake twice - a duplicate "
                "is preferred to dropping one for good."
            ),
            level="warning",
        )

    @staticmethod
    def _identifier(event: dict[str, Any]) -> str | None:
        """The entry's Slack id, or None when it carries none.

        An entry with no id is never suppressed: nothing tells a re-delivery apart from a genuinely
        distinct entry, and the requirement ranks a miss above a duplicate.
        """
        identifier = event.get("id")

        return None if identifier is None else str(identifier)

    @staticmethod
    def _timestamp_of(event: dict[str, Any]) -> int | None:
        """The event's creation time, or None when the entry carries nothing usable.

        Slack stamps every audit entry; absence is tolerated only so a malformed page cannot crash
        the cycle. The entry is still forwarded, and the only casualty is the event-lag figure.
        """
        try:
            return int(event["date_create"])
        except (KeyError, TypeError, ValueError):
            return None

    def _newest_date(self, entries: list[dict[str, Any]]) -> datetime | None:
        """The newest usable creation time in the batch, or None when no entry carries one."""
        stamps = [stamp for stamp in (self._timestamp_of(entry) for entry in entries) if stamp is not None]
        if not stamps:
            return None

        return datetime.fromtimestamp(max(stamps), tz=UTC).replace(tzinfo=None)
