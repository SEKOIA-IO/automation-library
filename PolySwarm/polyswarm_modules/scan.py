"""How the Scan actions wait for a new scan to finish.

The client's own wait_for looks the scan up once a second for as long as it is
allowed to wait, which at the 600 second ceiling is about 600 requests for one
playbook step. Waiting here uses the same schedule as the sandbox poller
instead: a short first check that doubles up to a low ceiling, so a fast scan
is answered in seconds and a slow one is not hammered.
"""

import time
from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from polyswarm_api.api import PolyswarmAPI

from polyswarm_modules.sandbox import INITIAL_POLL_INTERVAL, POLL_BACKOFF_FACTOR, SUBMIT_POLL_INTERVAL_CEILING

# A scan waits on engines that can answer slowly, but the SDK's own default of
# fifteen minutes is the kind of blocked playbook run the sandbox actions were
# written to avoid, so the wait is bounded here and exposed to the analyst
# instead. The ceiling matches the longest scan window PolySwarm offers.
DEFAULT_MAX_WAIT_SECONDS: int = 300
MAX_WAIT_SECONDS_CEILING: int = 600
MIN_WAIT_SECONDS: int = 30


def wait_for_scan(api: PolyswarmAPI, instance: Any, timeout: float) -> Any:
    """Look a submitted scan up until it fails or its assertion window closes.

    Raises the client's own TimeoutException when the wait runs out first, so
    callers keep handling it exactly as they handled wait_for. The scan itself
    carries on at PolySwarm. The last lookup is made at the deadline, not
    before it, so a scan that finishes in the final interval is still returned.
    """
    deadline = time.monotonic() + timeout
    interval = INITIAL_POLL_INTERVAL

    while True:
        result = api.lookup(instance)
        if result.failed or result.window_closed:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ps_exceptions.TimeoutException(f"Timed out waiting for scan {int(instance)} to finish.")
        time.sleep(min(interval, remaining))
        interval = min(interval * POLL_BACKOFF_FACTOR, SUBMIT_POLL_INTERVAL_CEILING)
