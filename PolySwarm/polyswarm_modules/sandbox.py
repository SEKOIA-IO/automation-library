"""What the sandbox actions and the SandboxCompleted trigger agree on.

SandboxFile, SandboxUrl and SandboxIp submit a detonation, Report reads one, and
the trigger announces one that has finished. They have to agree on which task
statuses mean finished, on how a task is addressed, and on how long a playbook
may be made to wait, or the same task would read as done in one place and
running in another.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlencode

from polyswarm_api.api import PolyswarmAPI

from polyswarm_modules.client import CLIENT_ERRORS, failure_kind

# A sandbox task is done when it reaches one of these. Anything else is still in flight.
TERMINAL_STATUSES: frozenset[str] = frozenset({"SUCCEEDED", "FAILED"})

# Resource path the PolySwarm client itself uses to read a single sandbox task.
SANDBOX_TASK_ENDPOINT: str = "/sandbox/sandboxtask"

# Short first check, doubling up to a low ceiling: this wait is for an
# analyst watching the run, not the batch style poll a scheduled playbook
# would tolerate. The ceiling the interval doubles up to is passed in by each
# caller, because Report is polling a task it did not start and backs off
# further than the actions that just submitted one.
INITIAL_POLL_INTERVAL: float = 5.0
POLL_BACKOFF_FACTOR: float = 2.0
SUBMIT_POLL_INTERVAL_CEILING: float = 30.0
DEFAULT_MAX_WAIT_SECONDS: int = 60
# Hard ceiling. Blocking a playbook run for fifteen minutes is the behaviour
# this action family replaces, so even an analyst who asks to wait cannot
# push it past five minutes; the SandboxCompleted trigger is the way to
# learn about anything slower than that.
MAX_WAIT_SECONDS_CEILING: int = 300

# Per request timeout while a wait is polling, in place of the client's 60 second
# default. A status check is a small read that normally answers in well under a
# second, so fifteen seconds is generous for a healthy one, and it is what keeps
# a wait honest: the deadline is checked between lookups, so one lookup that
# hangs through every retry is the most a wait can run past it. At fifteen
# seconds that is about a minute, where at the default it was about four. The
# detonation itself is unaffected, since it runs at PolySwarm whatever the
# status check does.
POLL_REQUEST_TIMEOUT: float = 15.0
# Worst case a wait can run past max_wait_seconds, for the text a playbook
# author reads: four attempts at the polling timeout plus the retry backoff.
WAIT_OVERRUN_SECONDS: int = 70


@contextmanager
def polling_timeout(api: PolyswarmAPI, seconds: float = POLL_REQUEST_TIMEOUT) -> Iterator[None]:
    """Use a shorter per request timeout for the lookups made inside the block.

    The client reads its timeout when it builds each request, so setting it on
    the instance is enough. The previous value is restored on the way out, so
    the submission and the report read that follow keep the client's own
    timeout.
    """
    previous = getattr(api, "timeout", None)
    api.timeout = min(previous, seconds) if previous else seconds
    try:
        yield
    finally:
        # Put back whatever was there, so later calls on the client keep its own timeout.
        api.timeout = previous


def report_url(api: PolyswarmAPI, task_id: str, community: str | None) -> str:
    """The API URL the PolySwarm client itself calls to read this task.

    Built from the client's own base URI and resource path rather than a
    hard coded host, so a non default deployment stays correct. The query is
    encoded rather than concatenated, since a community name is configuration
    and need not be URL safe.
    """
    query = {"sandbox_task_id": task_id}
    if community:
        query["community"] = community
    return f"{api.uri}{SANDBOX_TASK_ENDPOINT}?{urlencode(query)}"


def poll_until_terminal(
    api: PolyswarmAPI,
    task: Any,
    max_wait_seconds: int,
    interval_ceiling: float,
    log: Callable[..., Any],
) -> Any:
    """Poll a sandbox task until it reaches a terminal status or the wait ceiling, whichever comes first.

    The interval starts at INITIAL_POLL_INTERVAL and doubles each round,
    capped at interval_ceiling, so a fast provider gets an answer in seconds
    and a slow one is not polled every few seconds for the whole wait. The
    still-processing signal is the provider's own task status: anything
    outside TERMINAL_STATUSES is in progress. A failed status check is logged
    and retried rather than ending the wait, since the task itself carries on.

    The deadline is checked between status checks, so a wait can run past it
    by one check, bounded by POLL_REQUEST_TIMEOUT (see WAIT_OVERRUN_SECONDS).
    A task still running at the deadline is returned as it stands, not raised.
    """
    with polling_timeout(api):
        return _poll(api, task, max_wait_seconds, interval_ceiling, log)


def _poll(
    api: PolyswarmAPI,
    task: Any,
    max_wait_seconds: int,
    interval_ceiling: float,
    log: Callable[..., Any],
) -> Any:
    deadline = time.monotonic() + max_wait_seconds
    interval = INITIAL_POLL_INTERVAL

    while task.status not in TERMINAL_STATUSES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
        interval = min(interval * POLL_BACKOFF_FACTOR, interval_ceiling)
        try:
            task = api.sandbox_task_status(task.id)
        except CLIENT_ERRORS as exc:
            log(f"Sandbox status check failed ({failure_kind(exc)}), retrying", level="warning")

    return task
