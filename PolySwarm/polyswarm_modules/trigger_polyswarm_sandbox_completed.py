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
from polyswarm_modules.client import CLIENT_ERRORS, RETRY_TOTAL, build_client, failure_kind
from polyswarm_modules.coerce import as_optional_text
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

# How many consecutive failed lookups a single task gets before we stop following
# it. A task whose lookup fails every time is a problem with that task, not with
# the account, and polling it for six hours would spend lookups other tasks need.
MAX_LOOKUP_FAILURES: int = 5

# When at least this many lookups ran in one cycle and every one of them failed,
# the cause is the service rather than the tasks, so the cycle fails and backs
# off instead of charging the failures to the tasks.
OUTAGE_MIN_LOOKUPS: int = 2

# HTTP statuses that mean the account or the key is the problem, whichever task
# was being read. 429 is raised by the client as UsageLimitsExceededException and
# kept here as well so a bare status is read the same way.
ACCOUNT_WIDE_STATUSES: frozenset[int] = frozenset({401, 403, 429})

# The task listing returns at most this many tasks, the newest first. The
# endpoint answers no first page above ten and no page past the first.
PAGE_SIZE: int = 10

# Module level so the formatter has no parenthesised exception list to rewrite.
ACCOUNT_WIDE_ERRORS: tuple[type[Exception], ...] = (
    ps_exceptions.UsageLimitsExceededException,
    ps_exceptions.TimeoutException,
    RequestException,
)

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
        "page is followed here until it finishes. When more tasks than this are running at once, "
        "the ones not checked this poll are checked on the next, so those completions are late.",
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

    @property
    def last_heartbeat_threshold(self) -> int:  # type: ignore[override]
        """How long without a sign of life before the platform restarts this trigger.

        The SDK default is zero, which switches the check off, so heartbeat()
        did nothing until this was set. The longest healthy gap is one poll (a
        listing that retries on a slow endpoint) followed by the longer of the
        poll interval and the largest error back off, so the threshold is
        twice that back off or three poll intervals, plus the listing time.
        Read before the configuration is attached, it answers zero, which the
        SDK reads as no check.
        """
        if not getattr(self, "configuration", None):
            return 0
        listing = (RETRY_TOTAL + 1) * TASK_LIST_TIMEOUT
        return max(3 * self.configuration.frequency, 2 * MAX_BACKOFF_SECONDS) + listing

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
        known_before = already_emitted | set(self._in_flight())
        emitted = 0
        on_page: set[str] = set()

        page = self._recent_tasks()
        self._warn_if_page_rolled_past(page, known_before, first_run)

        for task in page:
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
            else:
                if self._emit(task, task_id):
                    emitted += 1
                already_emitted.add(task_id)

        if first_run:
            self._mark_initialised()
            # Say this out loud. A first run deliberately emits nothing, and an
            # operator who has just deployed the trigger and sees silence has no
            # way to tell that apart from a trigger that does not work. One line
            # naming what was skipped and what happens next is the difference
            # between a working deployment and a support ticket.
            waiting = len(self._in_flight())
            self.log(
                f"First poll: recorded {len(already_emitted)} detonations that had already finished, "
                f"without starting a playbook run for any of them, and is now following {waiting} still "
                "running. From here, one event is sent for each detonation as it finishes.",
                level="info",
            )

        return emitted + self._check_in_flight(already_emitted, on_page)

    def _warn_if_page_rolled_past(self, page: list[Any], known_before: set[str], first_run: bool) -> None:
        """Say so when the newest page shares nothing with what this trigger has seen.

        The listing shows only the newest ten tasks and cannot be paged, so a
        task created, finished and pushed off the page between two polls is
        invisible to this trigger. A page in which every task is new is the one
        sign of that this trigger can observe: it may have rolled past work it
        never saw. It also fires for a page of ten tasks that all started since
        the last poll and are still running, which is harmless, hence "may".
        """
        if first_run or not page:
            return
        ids = [task_id for task_id in (self._task_id(task) for task in page) if task_id]
        if ids and known_before.isdisjoint(ids):
            self.log(
                f"None of the {len(ids)} tasks on the newest page was seen on an earlier poll, so the page "
                "may have moved past detonations that started and finished between two polls. Those "
                "cannot be listed any more and will not produce an event. A shorter poll frequency "
                "narrows the gap.",
                level="warning",
            )

    def _emit(self, task: Any, task_id: str) -> bool:
        """Send the event for a terminal task if the configuration wants it.

        A terminal status is final, so the task is recorded as handled whether
        or not it was sent. A filtered out task is recorded too: left out of the
        store it would be judged again on every poll while it stays on the page,
        and an operator who later turned emit_failed on or changed the sandbox
        would see every such task fire at once. Recording also takes it out of
        the in flight set.
        """
        if not self._is_reportable(task):
            self._remember(task_id)
            return False
        self.send_event(self._event_name(task, task_id), self._build_event(task, task_id).model_dump())
        self._remember(task_id)
        return True

    def _check_in_flight(self, already_emitted: set[str], on_page: set[str]) -> int:
        """Look up, by identifier, the running tasks that the newest page no longer shows.

        Tasks still on the page were judged from the page itself, which is as
        fresh as a lookup, so they are skipped. The least recently checked tasks
        go first. A lookup error is charged to that one task, logged, and the
        task is dropped after MAX_LOOKUP_FAILURES in a row, so one task that
        never loads cannot put the whole trigger into back off. An error that
        says the account or the service is the problem (see _is_account_wide)
        is raised for the caller to back off from, and so is a cycle in which
        every lookup failed. The loop also stops once it has spent its
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
        failed: list[tuple[str, Exception]] = []
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
            except CLIENT_ERRORS as error:
                if self._is_account_wide(error):
                    raise
                failed.append((task_id, error))
                continue
            self._clear_lookup_failures(task_id)
            if not self._is_terminal(task):
                continue
            if self._emit(task, task_id):
                emitted += 1
            already_emitted.add(task_id)

        if failed and len(failed) == checked and checked >= OUTAGE_MIN_LOOKUPS:
            # Nothing came back at all, which points at the service and not at
            # the tasks. Do not spend the tasks' failure budget on it.
            raise failed[-1][1]
        for task_id, lookup_error in failed:
            self._charge_lookup_failure(task_id, lookup_error)
        return emitted

    @staticmethod
    def _is_account_wide(error: Exception) -> bool:
        """Whether a lookup error says the account, the key or the connection is the problem.

        Read from what the client raises. A 429 is UsageLimitsExceededException.
        A 401 or 403 is the client's plain RequestException carrying the status
        on its request. A dropped connection or a timeout is requests' own
        RequestException, which is a different class from the client's. A 404
        is NotFoundException, a 422 FailedInstanceException and a 204
        NoResultsException, which concern one task and are not account wide.
        Any other status, a 5xx included, is ambiguous for a single lookup, so
        it is charged to the task and the all lookups failed check in the
        caller catches a real outage.
        """
        if isinstance(error, ACCOUNT_WIDE_ERRORS):
            return True
        status = getattr(getattr(error, "request", None), "status_code", None)
        return isinstance(status, int) and status in ACCOUNT_WIDE_STATUSES

    def _charge_lookup_failure(self, task_id: str, error: Exception) -> None:
        """Count one failed lookup against a task, and stop following it after too many."""
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            record = in_flight.get(task_id)
            if record is None:
                return
            failures = int(record.get("failures", 0)) + 1
            if failures >= MAX_LOOKUP_FAILURES:
                del in_flight[task_id]
            else:
                in_flight[task_id] = {**record, "failures": failures}
            cache[IN_FLIGHT_KEY] = in_flight
        if failures >= MAX_LOOKUP_FAILURES:
            self.log(
                f"Stopped following sandbox task {task_id} after {failures} failed lookups in a row "
                f"({failure_kind(error)}). Its completion will not produce an event",
                level="warning",
            )
        else:
            self.log(
                f"Could not look up running sandbox task {task_id} ({failure_kind(error)}), "
                f"failure {failures} of {MAX_LOOKUP_FAILURES}",
                level="warning",
            )

    def _clear_lookup_failures(self, task_id: str) -> None:
        with self._store as cache:
            in_flight = dict(cache.get(IN_FLIGHT_KEY, {}))
            record = in_flight.get(task_id)
            if record and record.get("failures"):
                in_flight[task_id] = {key: value for key, value in record.items() if key != "failures"}
                cache[IN_FLIGHT_KEY] = in_flight

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
        reads one task and does not depend on the listing. That covers a task
        seen running at some poll. A task created, finished and pushed off the
        page entirely between two polls is never seen, and _warn_if_page_rolled_past
        reports the one sign of it that exists. Revisit the page limit when that
        endpoint is fixed.
        """
        return list(islice(self.client.sandbox_my_tasks_list(limit=PAGE_SIZE), PAGE_SIZE))

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
        community = as_optional_text(getattr(task, "community", None)) or self.module.configuration.community
        instance_id = as_optional_text(getattr(task, "instance_id", None))
        sha256 = as_optional_text(getattr(task, "sha256", None)) or ""

        portal_url = None
        if sha256 and instance_id:
            portal_url = f"{PORTAL_BASE}/{sha256}/{instance_id}"

        return SandboxCompletedEvent(
            sandbox_task_id=task_id,
            sha256=sha256,
            sandbox=as_optional_text(getattr(task, "sandbox", None)) or "",
            status=str(getattr(task, "status", "") or "").upper(),
            community=community,
            instance_id=instance_id,
            created=as_optional_text(getattr(task, "created", None)),
            expiration=as_optional_text(getattr(task, "expiration", None)),
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
                evicted = oldest[: len(in_flight) - MAX_IN_FLIGHT_TASKS]
                for key in evicted:
                    del in_flight[key]
                self.log(
                    f"Following more than {MAX_IN_FLIGHT_TASKS} running sandbox tasks, so the {len(evicted)} "
                    "oldest are no longer followed and their completion will not produce an event",
                    level="warning",
                )
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
        # The loop is alive and waiting, which is not the hang the platform
        # check exists to catch, and a restart would not cure an API outage.
        self.heartbeat()
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
