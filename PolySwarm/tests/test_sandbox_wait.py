from unittest.mock import MagicMock, patch

import pytest
from requests import RequestException

from polyswarm_modules.sandbox import POLL_REQUEST_TIMEOUT, WAIT_OVERRUN_SECONDS, poll_until_terminal
from tests.helpers import autospec_api


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    fake = _Clock()
    with patch("polyswarm_modules.sandbox.time") as mock_time:
        mock_time.monotonic.side_effect = fake.monotonic
        mock_time.sleep.side_effect = fake.sleep
        yield fake


def _task(status: str) -> MagicMock:
    task = MagicMock()
    task.status = status
    task.id = "t1"
    return task


def test_a_wait_that_reaches_its_deadline_returns_the_task_still_running(clock: _Clock) -> None:
    api = autospec_api()
    api.sandbox_task_status.return_value = _task("RUNNING")

    result = poll_until_terminal(api, _task("RUNNING"), 40, 30.0, MagicMock())

    assert result.status == "RUNNING"
    assert clock.now == 40


def test_status_checks_use_the_short_timeout_and_the_client_timeout_is_restored(clock: _Clock) -> None:
    api = autospec_api()
    original = api.timeout
    seen: list[float] = []

    def status(_task_id):
        seen.append(api.timeout)
        return _task("SUCCEEDED")

    api.sandbox_task_status.side_effect = status

    poll_until_terminal(api, _task("RUNNING"), 300, 30.0, MagicMock())

    assert seen == [POLL_REQUEST_TIMEOUT]
    assert api.timeout == original


def test_the_client_timeout_is_restored_when_a_status_check_raises_unexpectedly(clock: _Clock) -> None:
    api = autospec_api()
    original = api.timeout
    api.sandbox_task_status.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        poll_until_terminal(api, _task("RUNNING"), 300, 30.0, MagicMock())

    assert api.timeout == original


def test_a_wait_overruns_its_deadline_by_at_most_one_status_check(clock: _Clock) -> None:
    """The documented bound: the deadline is checked between checks, so one slow check is the overrun."""
    api = autospec_api()

    def slow_status(_task_id):
        clock.now += WAIT_OVERRUN_SECONDS  # a check that hangs through every retry
        raise RequestException("timed out")

    api.sandbox_task_status.side_effect = slow_status

    result = poll_until_terminal(api, _task("RUNNING"), 12, 30.0, MagicMock())

    assert result.status == "RUNNING"
    assert clock.now <= 12 + WAIT_OVERRUN_SECONDS
    assert api.sandbox_task_status.call_count == 1
