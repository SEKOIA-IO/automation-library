"""Trigger that emits one event per completed PolySwarm sandbox detonation.

Route chosen: polling. Not PolySwarm notification webhooks.

Why. The PolySwarm client does expose notification_webhook_create with a
sandbox_done event, so the producer side of a webhook design exists. The
consumer side does not. A Sekoia trigger is a container that the orchestrator
starts with no inbound route: the only HTTP server the SDK stands up is
sekoia_automation.trigger.LivenessHandler, which answers GET /health and
returns 404 for every other path, and the port it binds comes from a local
liveness_port config file, not from a published ingress. Every URL the SDK
hands a trigger (callback_url, logs_url, secrets_url, intake_url) is outbound
and bearer authenticated: they are endpoints the trigger posts to, not an
address a third party can call. Nothing in the SDK allocates or reports a
publicly routable URL for the running trigger, so the trigger cannot tell
PolySwarm where to deliver sandbox_done. A survey of the public
SEKOIA-IO/automation-library confirms the shape: no module there receives an
inbound webhook, while polling triggers backed by sekoia_automation.storage
are the standard pattern. Claiming a webhook receiver here would ship a
capability the runtime does not have.

What would have to be true for the webhook route to win. Sekoia would have to
give a trigger a stable, publicly reachable callback URL, either injected as a
config value at start up the way callback_url is, or through a gateway that
maps a path to the trigger container. Given that, the better design flips:
notification_webhook_create registers that URL with the sandbox_done event,
the trigger verifies the HMAC signature carried by the secret it generated,
and detonations arrive in seconds with no polling cost and no window in which
a burst of tasks could outrun the scan. That question is worth asking Sekoia
directly, since it is the only thing standing between this file and a push
design.

What this trigger does instead. Every poll it reads the newest sandbox tasks
created by the configured account and emits one event for each task that has
reached a terminal status and has not been emitted before. A detonation takes
minutes, and the task listing can only be read one page of ten at a time, so a
busy account can push a task off that page while it is still running. Each task
seen running is therefore remembered, and is looked up by its own identifier on
later polls until it finishes, whether or not it is still on the newest page.
What it emitted, and what it is still waiting on, lives in the SDK's
PersistentJSON store so a restart does not replay.

The first poll against an empty store emits nothing. It records the tasks that
are already finished as emitted and starts tracking the ones still running.
Without that, every deploy, and every restart the platform performs after it
has lost the store, would start a playbook run for each finished task on the
newest page, however old. The price is that a task which finished while the
store was missing is not reported.

The event carries the identity of the detonation and where to fetch the
report, not the report body: a sandbox report is routinely megabytes and
belongs behind the Report action, which the receiving playbook calls with the
sha256 and sandbox from the event.
"""

from datetime import UTC, datetime
from functools import cached_property
from itertools import islice
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI
from pydantic import BaseModel, Field
from requests import RequestException
from sekoia_automation.exceptions import SendEventError
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import build_client
from polyswarm_modules.sandbox import TERMINAL_STATUSES, report_url

# Base of the PolySwarm portal page for an artifact instance.
PORTAL_BASE: str = "https://polyswarm.network/scan/results/file"

# How many emitted task identifiers we keep in the persistent store. The
# listing only ever shows the newest ten tasks, so an identifier can only be
# evicted long after the task fell off that page, and it cannot come back to
# be emitted a second time.
MAX_TRACKED_TASKS: int = 5000

# How many running tasks we follow by identifier at once. Past this the oldest
# are dropped, so a burst of submissions cannot grow the store without bound.
MAX_IN_FLIGHT_TASKS: int = 1000

# What share of the poll interval the identifier lookups may spend. They run one
# after another against an endpoint whose latency we have not measured, so a
# large max_tasks_per_cycle could otherwise make a poll outlast its own
# frequency and leave the trigger permanently behind. Stopping early is safe:
# the least recently checked tasks go first, so whatever is skipped is first in
# line next time.
IN_FLIGHT_BUDGET_SHARE: float = 0.5

# How long a task may stay in flight before we stop looking for it. A sandbox
# detonation takes minutes, so a task still not terminal after this long is
# stuck on the PolySwarm side, and polling it forever would only spend lookups
# that finished tasks need. This is a chosen ceiling, not a measured one.
IN_FLIGHT_MAX_AGE_SECONDS: int = 6 * 3600

# Upper bound on the error back off, so a long outage does not push the next
# attempt days into the future.
MAX_BACKOFF_SECONDS: int = 1800

STORE_FILE_NAME: str = "sandbox_completed_trigger.json"
TASK_LIST_TIMEOUT: int = 120
STORE_KEY: str = "emitted_task_ids"
IN_FLIGHT_KEY: str = "in_flight_tasks"
INITIALISED_KEY: str = "initialised"


class SandboxCompletedConfiguration(BaseModel):
    """Per trigger configuration, set by the analyst in the playbook."""

    frequency: int = Field(
        default=60,
        ge=10,
        le=86400,
        description="Seconds to wait between two polls of the PolySwarm sandbox task list",
    )
    sandbox: str | None = Field(
        default=None,
        description="Only emit events for this sandbox provider slug, for example 'cape' or 'triage'. "
        "Leave empty to emit for every provider.",
    )
    emit_failed: bool = Field(
        default=True,
        description="Emit an event for detonations that ended in FAILED as well as SUCCEEDED",
    )
    max_tasks_per_cycle: int = Field(
        default=50,
        ge=1,
        le=500,
        description="How many still running sandbox tasks to look up by identifier on each poll, "
        "in addition to the newest page of ten. A task that is running when it falls off the newest "
        "page is followed here until it finishes, so a completion is only delayed, not missed, "
        "when more tasks than this are running at once. The ones not checked this poll are "
        "checked on the next.",
    )
    page_size: int = Field(
        default=10,
        ge=1,
        le=10,
        description="How many sandbox tasks to request per page from the PolySwarm API",
    )


class SandboxCompletedEvent(BaseModel):
    """One completed sandbox detonation, as handed to the playbook."""

    sandbox_task_id: str = Field(..., description="Identifier of the sandbox task")
    sha256: str = Field(..., description="SHA256 of the detonated artifact")
    sandbox: str = Field(..., description="Sandbox provider that ran the detonation")
    status: str = Field(..., description="Terminal status of the task, SUCCEEDED or FAILED")
    community: str | None = Field(default=None, description="PolySwarm community the task ran in")
    instance_id: str | None = Field(default=None, description="Artifact instance the detonation belongs to")
    created: str | None = Field(default=None, description="When the task was created, as reported by PolySwarm")
    expiration: str | None = Field(default=None, description="When PolySwarm expires the task, if it reports one")
    report_available: bool = Field(
        ...,
        description="Whether a report can be fetched for this detonation. The event never carries the "
        "report itself: fetch it with the Report action using the hash and sandbox from this event",
    )
    report_url: str = Field(..., description="PolySwarm API URL that returns this sandbox task and its report")
    portal_url: str | None = Field(default=None, description="PolySwarm portal page for the artifact instance")
    sandbox_artifact_count: int = Field(default=0, description="Number of artifacts the detonation produced")
    detected_at: str = Field(..., description="When this trigger observed the task as complete, UTC, ISO 8601")


class SandboxCompleted(Trigger):
    """Emit an event whenever a PolySwarm sandbox detonation finishes.

    Replaces the blocking wait inside the Report action: instead of holding a
    playbook run open for up to fifteen minutes, a submission finishes on
    PolySwarm's schedule and this trigger starts the playbook that handles it.
    """

    module: PolyswarmModule
    configuration: SandboxCompletedConfiguration  # type: ignore[assignment]
    results_model = SandboxCompletedEvent

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._consecutive_failures = 0

    @cached_property
    def _store(self) -> PersistentJSON:
        """Persistence for emitted identifiers and in flight tasks, provided by the SDK."""
        return PersistentJSON(STORE_FILE_NAME, self.data_path)

    @cached_property
    def client(self) -> PolyswarmAPI:
        # The task listing endpoint is slow, and it falls off a cliff with page
        # size. Measured against the live service on 2026-09-22: a page of 1 or
        # 10 answers in about 7 seconds, a page of 20 or 50 never answers at all
        # inside 200 seconds. Hence a page size capped at 10 above, and a
        # ceiling well above the client default of 30 seconds here, which this
        # trigger can afford because it runs on its own schedule rather than
        # inside a playbook run. Raise the cap once the endpoint is fixed.
        # Built through the shared factory so retries on safe methods are
        # configured the same way for every PolySwarm component, with the
        # longer timeout this endpoint needs passed through rather than lost.
        return build_client(self.module.configuration, timeout=TASK_LIST_TIMEOUT)

    def run(self) -> None:
        """Poll until Sekoia stops the trigger.

        Trigger.execute calls this in a loop of its own, so a return here is a
        restart rather than an exit. Every failure path inside the loop backs
        off before the next attempt: a trigger that raised on an API error
        would be restarted immediately by the runtime and hammer PolySwarm.
        """
        self.log("PolySwarm sandbox completion trigger started", level="info")

        while self.running:
            try:
                emitted = self.poll_once()
            except (ps_exceptions.PolyswarmException, RequestException) as error:
                self._back_off("PolySwarm API error while listing sandbox tasks", error)
                continue
            except SendEventError as error:
                self._back_off("Could not send a sandbox completion event to Sekoia", error)
                continue
            except Exception as error:  # a trigger must not die on an unexpected error
                self._back_off("Unexpected error while polling PolySwarm sandbox tasks", error)
                continue

            self._consecutive_failures = 0
            self.heartbeat()
            if emitted:
                self.log(f"Emitted {emitted} completed sandbox detonation events", level="info")
            self._wait(self.configuration.frequency)

    def poll_once(self) -> int:
        """Run a single poll and return how many events were emitted.

        Exceptions are deliberately allowed out so the caller decides the back
        off. Keeping the cycle a separate method also keeps it testable without
        an infinite loop.
        """
        first_run = not self._is_initialised()
        already_emitted = set(self._emitted_task_ids())
        emitted = 0
        on_page: set[str] = set()

        for task in self._recent_tasks():
            task_id = self._task_id(task)
            if not task_id or task_id in already_emitted:
                continue
            on_page.add(task_id)

            if not self._is_terminal(task):
                if self._matches_sandbox(task):
                    self._track_in_flight(task_id)
                continue

            if first_run:
                # Already finished before this trigger ever looked: record it so
                # it is not replayed later, but do not start a playbook for it.
                self._remember(task_id)
                already_emitted.add(task_id)
            elif self._emit(task, task_id):
                already_emitted.add(task_id)
                emitted += 1

        if first_run:
            self._mark_initialised()

        return emitted + self._check_in_flight(already_emitted, on_page)

    def _emit(self, task: Any, task_id: str) -> bool:
        """Send the event for a terminal task if the configuration wants it.

        The task leaves the in flight set whether or not it was sent, because a
        terminal status is final: a filtered out task is not worth another lookup.
        """
        if not self._is_reportable(task):
            self._untrack_in_flight(task_id)
            return False
        self.send_event(self._event_name(task, task_id), self._build_event(task, task_id).model_dump())
        self._remember(task_id)
        return True

    def _check_in_flight(self, already_emitted: set[str], on_page: set[str]) -> int:
        """Look up, by identifier, the running tasks that the newest page no longer shows.

        Tasks still on the page were judged from the page itself, which is as
        fresh as a lookup, so they are skipped. The least recently checked tasks
        go first and an error is recorded against the task before it is
        re-raised, so one task that always fails to load rotates to the back of
        the queue instead of starving the others, while the caller still backs
        off from a PolySwarm outage. The loop also stops once it has spent its
        share of the poll interval, so a slow endpoint delays a completion
        rather than stalling the whole trigger. At least one task is always
        looked up, otherwise a frequency shorter than a single lookup would
        make no progress at all.
        """
        self._drop_expired_in_flight()
        in_flight = self._in_flight()
        candidates = sorted(
            (task_id for task_id in in_flight if task_id not in on_page),
            key=lambda task_id: in_flight[task_id]["last_checked"],
        )

        emitted = 0
        deadline = self._now() + self.configuration.frequency * IN_FLIGHT_BUDGET_SHARE
        checked = 0
        for task_id in candidates[: self.configuration.max_tasks_per_cycle]:
            if checked and self._now() >= deadline:
                self.log(
                    f"Ran out of time looking up running sandbox tasks after {checked} of "
                    f"{len(candidates)}. The rest are first in line on the next poll",
                    level="info",
                )
                break
            checked += 1
            if task_id in already_emitted:
                self._untrack_in_flight(task_id)
                continue
            self._touch_in_flight(task_id)
            try:
                task = self.client.sandbox_task_status(task_id)
            except ps_exceptions.NotFoundException:
                # PolySwarm no longer knows the task, so it can never finish for us.
                self._untrack_in_flight(task_id)
                continue
            if not self._is_terminal(task):
                continue
            if self._emit(task, task_id):
                already_emitted.add(task_id)
                emitted += 1
        return emitted

    def _recent_tasks(self) -> list[Any]:
        """The newest sandbox tasks for this account, one page only.

        sandbox_my_tasks_list returns a generator that pages through the whole
        history, so it has to be bounded: an unbounded walk would re-read every
        task the account ever created on every cycle.

        The bound is one page, deliberately. Measured against the live service
        on 2026-09-22, the endpoint answers a first page of ten in about seven
        seconds, but a request carrying a page offset does not answer at all
        inside two minutes, and neither does a first page of twenty or more. A
        second page would therefore hang this cycle rather than fetch anything,
        so the trigger reads the newest page and waits for the next poll.

        That page alone would miss a detonation that outlasts ten newer
        submissions, since it would leave the page before finishing. Running
        tasks are therefore followed by identifier, see _check_in_flight, which
        reads one task and does not depend on the listing. Revisit the page
        limit when that endpoint is fixed.
        """
        page_size = self.configuration.page_size
        return list(islice(self.client.sandbox_my_tasks_list(limit=page_size), page_size))

    @staticmethod
    def _is_terminal(task: Any) -> bool:
        return str(getattr(task, "status", "") or "").upper() in TERMINAL_STATUSES

    def _matches_sandbox(self, task: Any) -> bool:
        wanted = self.configuration.sandbox
        return not wanted or str(getattr(task, "sandbox", "") or "") == wanted

    def _is_reportable(self, task: Any) -> bool:
        if not self._is_terminal(task):
            return False
        if str(getattr(task, "status", "") or "").upper() == "FAILED" and not self.configuration.emit_failed:
            return False
        return self._matches_sandbox(task)

    def _build_event(self, task: Any, task_id: str) -> SandboxCompletedEvent:
        community = self._as_text(getattr(task, "community", None)) or self.module.configuration.community
        instance_id = self._as_text(getattr(task, "instance_id", None))
        sha256 = self._as_text(getattr(task, "sha256", None)) or ""

        portal_url = None
        if sha256 and instance_id:
            portal_url = f"{PORTAL_BASE}/{sha256}/{instance_id}"

        return SandboxCompletedEvent(
            sandbox_task_id=task_id,
            sha256=sha256,
            sandbox=self._as_text(getattr(task, "sandbox", None)) or "",
            status=str(getattr(task, "status", "") or "").upper(),
            community=community,
            instance_id=instance_id,
            created=self._as_text(getattr(task, "created", None)),
            expiration=self._as_text(getattr(task, "expiration", None)),
            # The task listing never inlines a report body, verified against the
            # live service on 2026-09-22, so reading one here would make this
            # field false for every event ever emitted. A succeeded detonation
            # is one whose report can be fetched, which is what a playbook
            # branching on this field actually wants to know.
            report_available=str(getattr(task, "status", "") or "").upper() == "SUCCEEDED",
            report_url=report_url(self.client, task_id, community),
            portal_url=portal_url,
            sandbox_artifact_count=len(getattr(task, "sandbox_artifacts", None) or []),
            detected_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _event_name(task: Any, task_id: str) -> str:
        sandbox = getattr(task, "sandbox", None) or "sandbox"
        return f"PolySwarm {sandbox} detonation {task_id} completed"

    @staticmethod
    def _task_id(task: Any) -> str | None:
        raw = getattr(task, "id", None)
        if raw is None:
            return None
        return str(raw)

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def _emitted_task_ids(self) -> list[str]:
        with self._store as cache:
            return list(cache.get(STORE_KEY, []))

    def _is_initialised(self) -> bool:
        """Whether an earlier poll has already seeded the store.

        A store written before this flag existed holds emitted identifiers, and
        counts as seeded, so an upgrade does not silently skip a poll's worth of
        completions.
        """
        with self._store as cache:
            return bool(cache.get(INITIALISED_KEY) or cache.get(STORE_KEY))

    def _mark_initialised(self) -> None:
        with self._store as cache:
            cache[INITIALISED_KEY] = True

    def _remember(self, task_id: str) -> None:
        """Record an identifier as emitted, flushed to disk immediately.

        The write happens after the event was accepted, once per event rather
        than once per cycle, so a restart between two events in the same cycle
        does not replay the ones that already went out. The task leaves the in
        flight set in the same write, so a restart cannot leave it in both.
        """
        with self._store as cache:
            known = list(cache.get(STORE_KEY, []))
            known.append(task_id)
            if len(known) > MAX_TRACKED_TASKS:
                known = known[-MAX_TRACKED_TASKS:]
            cache[STORE_KEY] = known
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            if in_flight.pop(task_id, None) is not None:
                cache[IN_FLIGHT_KEY] = in_flight

    def _in_flight(self) -> dict[str, dict[str, float]]:
        with self._store as cache:
            return dict(cache.get(IN_FLIGHT_KEY, {}))

    def _track_in_flight(self, task_id: str) -> None:
        """Start following a running task by identifier, unless it already is."""
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            if task_id in in_flight:
                return
            now = self._now()
            in_flight[task_id] = {"first_seen": now, "last_checked": now}
            if len(in_flight) > MAX_IN_FLIGHT_TASKS:
                oldest = sorted(in_flight, key=lambda key: in_flight[key]["first_seen"])
                for key in oldest[: len(in_flight) - MAX_IN_FLIGHT_TASKS]:
                    del in_flight[key]
            cache[IN_FLIGHT_KEY] = in_flight

    def _touch_in_flight(self, task_id: str) -> None:
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            if task_id in in_flight:
                in_flight[task_id] = {**in_flight[task_id], "last_checked": self._now()}
                cache[IN_FLIGHT_KEY] = in_flight

    def _untrack_in_flight(self, task_id: str) -> None:
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            if in_flight.pop(task_id, None) is not None:
                cache[IN_FLIGHT_KEY] = in_flight

    def _drop_expired_in_flight(self) -> None:
        cutoff = self._now() - IN_FLIGHT_MAX_AGE_SECONDS
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            kept = {key: value for key, value in in_flight.items() if value["first_seen"] >= cutoff}
            if len(kept) != len(in_flight):
                self.log(
                    f"Stopped following {len(in_flight) - len(kept)} sandbox tasks that never finished",
                    level="warning",
                )
                cache[IN_FLIGHT_KEY] = kept

    @staticmethod
    def _now() -> float:
        return datetime.now(UTC).timestamp()

    def _back_off(self, context: str, error: Exception) -> None:
        """Log a failure without leaking the API key, then wait longer each time."""
        self._consecutive_failures += 1
        self.log(f"{context}: {self._redact(error)}", level="error")
        delay = min(self.configuration.frequency * (2**self._consecutive_failures), MAX_BACKOFF_SECONDS)
        self.log(f"Backing off for {delay} seconds after {self._consecutive_failures} consecutive failures", "info")
        self._wait(delay)

    def _redact(self, error: Exception) -> str:
        """Strip the API key out of anything headed for a log line.

        The PolySwarm client renders request parameters into some of its error
        messages, so the message is never trusted to be key free.
        """
        message = str(error) or error.__class__.__name__
        apikey = self.module.configuration.apikey
        if apikey:
            message = message.replace(apikey, "[REDACTED]")
        return message

    def _wait(self, seconds: float) -> None:
        """Sleep, but wake up at once when Sekoia asks the trigger to stop."""
        self._stop_event.wait(seconds)
