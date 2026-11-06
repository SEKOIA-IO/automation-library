from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rapid7_insightvm.asset_connector.models.window import Window

NOW = datetime(2026, 10, 28, 12, 0, 0, 123456, tzinfo=UTC)


def test_first_window_collects_every_open_finding():
    assert Window.next_from(None, NOW) == Window(current_time="2026-10-28T11:00:00Z")


def test_next_window_starts_at_the_previous_one():
    window = Window.next_from("2026-10-27T11:00:00Z", NOW)
    assert window == Window(comparison_time="2026-10-27T11:00:00Z", current_time="2026-10-28T11:00:00Z")


def test_first_run():
    assert Window(current_time="2026-10-28T11:00:00Z").first_run is True
    assert Window(current_time="2026-10-28T11:00:00Z", comparison_time="2026-10-27T11:00:00Z").first_run is False


def test_too_short_window_is_skipped():
    # NOW - CLOUD_SYNC_DELAY = 11:00: a window must last at least MIN_WINDOW_DURATION (2 hours)
    assert Window.next_from("2026-10-28T09:30:00Z", NOW) is None
    assert Window.next_from("2026-10-28T09:00:00Z", NOW) is not None


def test_full_resync_only_applies_after_a_first_run():
    assert Window.next_from("2026-10-27T11:00:00Z", NOW, full_resync=True).full_resync is True
    assert Window.next_from(None, NOW, full_resync=True).full_resync is False


def test_window_stored_before_the_new_fields_is_read_with_their_defaults():
    stored = {
        "comparison_time": "2026-10-27T11:00:00Z",
        "current_time": "2026-10-28T11:00:00Z",
        "page": 3,
        "cursor": "c",
    }
    window = Window.model_validate(stored)
    assert (window.page, window.cursor, window.full_resync, window.short_attempts) == (3, "c", False, 0)


def test_retry_restarts_the_window_and_counts_the_attempt():
    window = Window(current_time="2026-10-28T11:00:00Z", page=3, cursor="c", full_resync=True)
    retried = window.retry().retry()
    assert (retried.page, retried.cursor, retried.short_attempts, retried.full_resync) == (0, None, 2, True)


def test_invalid_comparison_time_starts_a_first_run():
    assert Window.next_from("garbage", NOW).first_run is True


def test_window_is_validated_when_built():
    window = Window(current_time="2026-10-28T11:00:00Z")
    assert window.at_page(2, "next").model_dump() == {
        "current_time": "2026-10-28T11:00:00Z",
        "comparison_time": None,
        "page": 2,
        "cursor": "next",
        "full_resync": False,
        "short_attempts": 0,
    }
    with pytest.raises(ValidationError):
        window.at_page(-1, None)
    with pytest.raises(ValidationError):
        Window(current_time="2026-10-28T11:00:00Z", page="first")
