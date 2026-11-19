from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules.sandbox import POLL_REQUEST_TIMEOUT, WAIT_OVERRUN_SECONDS
from polyswarm_modules.scan import wait_for_scan
from tests.helpers import autospec_api


def _scan(*, closed: bool = False, failed: bool = False) -> MagicMock:
    result = MagicMock()
    result.window_closed = closed
    result.failed = failed
    return result


class _Clock:
    """A monotonic clock that only moves when the wait sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock():
    fake = _Clock()
    with patch("polyswarm_modules.scan.time") as mock_time:
        mock_time.monotonic.side_effect = fake.monotonic
        mock_time.sleep.side_effect = fake.sleep
        yield fake


def test_a_finished_scan_is_returned_without_sleeping(clock: _Clock) -> None:
    api = autospec_api()
    done = _scan(closed=True)
    api.lookup.return_value = done

    assert wait_for_scan(api, MagicMock(), 300) is done
    assert clock.sleeps == []
    assert api.lookup.call_count == 1


def test_a_failed_scan_is_returned_at_once(clock: _Clock) -> None:
    api = autospec_api()
    failed = _scan(failed=True)
    api.lookup.return_value = failed

    assert wait_for_scan(api, MagicMock(), 300) is failed


def test_polling_backs_off_and_the_last_check_lands_on_the_deadline(clock: _Clock) -> None:
    api = autospec_api()
    api.lookup.side_effect = [_scan(), _scan(), _scan(), _scan(), _scan(closed=True)]

    result = wait_for_scan(api, MagicMock(), 300)

    assert result.window_closed is True
    assert clock.sleeps == [5.0, 10.0, 20.0, 30.0]


def test_a_long_wait_costs_a_few_dozen_lookups_not_hundreds(clock: _Clock) -> None:
    api = autospec_api()
    api.lookup.return_value = _scan()
    instance = MagicMock()
    instance.__int__ = lambda self: 7

    with pytest.raises(ps_exceptions.TimeoutException):
        wait_for_scan(api, instance, 600)

    assert api.lookup.call_count < 30
    assert clock.now == 600


def test_the_wait_never_sleeps_past_the_deadline(clock: _Clock) -> None:
    api = autospec_api()
    api.lookup.return_value = _scan()
    instance = MagicMock()
    instance.__int__ = lambda self: 7

    with pytest.raises(ps_exceptions.TimeoutException):
        wait_for_scan(api, instance, 12)

    assert sum(clock.sleeps) == 12


def test_scan_lookups_use_the_short_polling_timeout_and_the_client_timeout_is_restored(clock: _Clock) -> None:
    api = autospec_api()
    original = api.timeout
    seen: list[float] = []

    def lookup(_instance):
        seen.append(api.timeout)
        return _scan(closed=True)

    api.lookup.side_effect = lookup

    wait_for_scan(api, MagicMock(), 300)

    assert seen == [POLL_REQUEST_TIMEOUT]
    assert api.timeout == original


def test_a_scan_wait_overruns_its_deadline_by_at_most_one_lookup(clock: _Clock) -> None:
    """The documented bound: the deadline is checked between lookups, so one slow lookup is the overrun."""
    api = autospec_api()
    instance = MagicMock()
    instance.__int__ = lambda self: 7

    def slow_lookup(_instance):
        clock.now += WAIT_OVERRUN_SECONDS  # a lookup that hangs through every retry
        return _scan()

    api.lookup.side_effect = slow_lookup

    with pytest.raises(ps_exceptions.TimeoutException):
        wait_for_scan(api, instance, 12)

    assert clock.now <= 12 + WAIT_OVERRUN_SECONDS
    assert api.lookup.call_count == 1
