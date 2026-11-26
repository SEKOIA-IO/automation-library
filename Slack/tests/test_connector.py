from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import orjson
import pytest
from pydantic import ValidationError
from sekoia_automation.connector import Connector
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from sekoia_automation.storage import PersistentJSON

from slack_modules import SlackAuditLogsModule
from slack_modules.connector import (
    SlackAuditLogsConnector,
    SlackAuditLogsConnectorConfiguration,
)
from slack_modules.errors import AuthenticationError, SlackAuditLogsError

CONFIGURATION = {"intake_key": "intake-key", "frequency": 42, "limit": 500}


def seconds_ago(seconds: int) -> int:
    return int(datetime.now(UTC).timestamp()) - seconds


def entry(event_id: str, date_create: int) -> dict:
    return {"id": event_id, "date_create": date_create, "action": "user_login"}


def slack_like(*pages: list[dict]):
    """A stand-in for `iter_pages` that, like Slack, only returns entries inside the window, and
    hands back a cursor per page which empties on the last one."""

    def iter_pages(self, oldest: int, latest: int, limit: int, cursor: str = ""):
        for index, page in enumerate(pages, start=1):
            inside = [event for event in page if oldest <= int(event["date_create"]) <= latest]
            yield inside, "" if index == len(pages) else f"cursor-{index}"

    return iter_pages


def empty_windows(calls: list[tuple[int, int, str]]):
    """Records every window requested and reports each one as empty and drained."""

    def iter_pages(self, oldest: int, latest: int, limit: int, cursor: str = ""):
        calls.append((oldest, latest, cursor))
        yield [], ""

    return iter_pages


@pytest.fixture
def module():
    module = SlackAuditLogsModule()
    module.configuration = {"token": "xoxp-test", "base_url": "https://api.slack.test/audit/v1"}
    return module


@pytest.fixture
def connector(module, tmp_path):
    connector = SlackAuditLogsConnector(module=module, data_path=tmp_path)
    connector.configuration = dict(CONFIGURATION)
    return connector


def watermarked(module: SlackAuditLogsModule, data_path: Path, at: int, **configuration) -> SlackAuditLogsConnector:
    """A connector resuming from a watermark at `at` (unix seconds).

    The watermark is seeded through context.json rather than by assigning `checkpoint.offset`:
    CheckpointTimestamp's setter is monotonic, so moving the watermark backwards is silently
    ignored and a test that tried it would exercise the default lookback instead.
    """
    (data_path / "context.json").write_text(
        orjson.dumps({"most_recent_date_seen": datetime.fromtimestamp(at, tz=UTC).isoformat()}).decode()
    )

    connector = SlackAuditLogsConnector(module=module, data_path=data_path)
    connector.configuration = SlackAuditLogsConnectorConfiguration(**{**CONFIGURATION, **configuration})
    return connector


def seed_progress(
    data_path: Path,
    window_start: int,
    window_end: int,
    cursor: str,
    pushed_ids: Iterable[str] = (),
    truncated: bool = False,
) -> None:
    """The pending.json an interrupted earlier cycle would have left behind."""
    (data_path / "pending.json").write_text(
        orjson.dumps(
            {
                "window_start": window_start,
                "window_end": window_end,
                "cursor": cursor,
                "pushed_ids": list(pushed_ids),
                "truncated": truncated,
            }
        ).decode()
    )


def stored_progress(data_path: Path) -> dict:
    return orjson.loads((data_path / "pending.json").read_bytes())


def forwarded_ids(connector: SlackAuditLogsConnector) -> list[str]:
    return [orjson.loads(event)["id"] for events, _ in connector.iterate() for event in events]


def test_frequency_comes_from_the_configuration(connector):
    assert connector.frequency == 42


def test_iterate_yields_json_strings_and_a_naive_utc_date(module, tmp_path, monkeypatch):
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    older, newer = start + 10, start + 20
    monkeypatch.setattr(type(connector.client), "iter_pages", slack_like([entry("a", older), entry("b", newer)]))

    batches = list(connector.iterate())

    events, last_event_date = batches[0]
    assert [orjson.loads(event)["id"] for event in events] == ["a", "b"]
    assert last_event_date == datetime.fromtimestamp(newer, tz=UTC).replace(tzinfo=None)
    assert last_event_date.tzinfo is None


def test_iterate_asks_slack_for_events_strictly_after_the_watermark(connector, monkeypatch):
    expected = connector.checkpoint.offset + 1
    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(type(connector.client), "iter_pages", empty_windows(calls))

    list(connector.iterate())

    assert calls[0][0] == expected
    assert calls[0][2] == ""  # no stored cursor for a window this connector has not seen before


def test_windows_are_walked_in_ascending_order_and_bounded_by_the_timebuffer(module, tmp_path, monkeypatch):
    start = seconds_ago(3 * 3600)
    connector = watermarked(module, tmp_path, start)
    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(type(connector.client), "iter_pages", empty_windows(calls))

    list(connector.iterate())

    ceiling = int(datetime.now(UTC).timestamp()) - connector.configuration.timebuffer
    windows = [(oldest, latest) for oldest, latest, _ in calls]

    assert len(windows) == 3  # three hours of backlog, one sub-window per hour
    assert windows == sorted(windows)  # oldest first, so progress stays expressible as a timestamp
    assert windows[0][0] == start + 1
    assert all(nxt[0] == cur[1] + 1 for cur, nxt in pairwise(windows))  # no gap, no overlap
    for oldest, latest in windows:
        assert oldest <= latest
        assert latest - oldest < connector.SUB_WINDOW_SECONDS
        assert latest <= ceiling


def test_no_window_is_requested_while_everything_is_inside_the_time_buffer(module, tmp_path, monkeypatch):
    connector = watermarked(module, tmp_path, seconds_ago(10))
    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(type(connector.client), "iter_pages", empty_windows(calls))

    assert list(connector.iterate()) == []
    assert calls == []


def test_the_watermark_only_advances_over_a_fully_drained_window(module, tmp_path, monkeypatch):
    start = seconds_ago(3 * 3600)
    connector = watermarked(module, tmp_path, start)

    def fail_on_the_second_window(self, oldest, latest, limit, cursor=""):
        if oldest > start + 1:
            raise SlackAuditLogsError("boom")
        yield [entry("a", oldest + 10)], ""

    monkeypatch.setattr(type(connector.client), "iter_pages", fail_on_the_second_window)

    with pytest.raises(SlackAuditLogsError):
        list(connector.iterate())

    # the end of the one window that drained - not the newest event it held, and nowhere near now
    assert connector.checkpoint.offset == start + connector.SUB_WINDOW_SECONDS


def test_a_drained_window_commits_its_end_and_clears_the_stored_progress(module, tmp_path, monkeypatch):
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(type(connector.client), "iter_pages", slack_like([entry("a", start + 5)]))

    list(connector.iterate())

    assert stored_progress(tmp_path) == {
        "window_start": None,
        "window_end": None,
        "cursor": "",
        "pushed_ids": [],
        "truncated": False,
    }
    # progress lives in its own file, so rewriting it cannot clobber the checkpoint's context.json
    assert orjson.loads((tmp_path / "context.json").read_bytes())["most_recent_date_seen"]
    assert connector.checkpoint.offset > start


def test_progress_is_persisted_after_a_push_and_a_fresh_connector_resumes_from_the_cursor(
    module, tmp_path, monkeypatch
):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)

    def one_page_then_the_budget_runs_out(self, oldest, latest, limit, cursor=""):
        yield [entry("a", oldest + 5)], "page-2"  # a cursor still pending: the window is unfinished

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page_then_the_budget_runs_out)

    assert forwarded_ids(connector) == ["a"]
    assert stored_progress(tmp_path) == {
        "window_start": start + 1,
        "window_end": start + 3600,
        "cursor": "page-2",
        "pushed_ids": ["a"],
        "truncated": False,
    }
    assert connector.checkpoint.offset == start  # the window is unfinished, so nothing is committed

    # a fresh container on the same data path carries on inside the window instead of restarting it
    resumed = SlackAuditLogsConnector(module=module, data_path=tmp_path)
    resumed.configuration = dict(CONFIGURATION)
    resumed_calls: list[tuple[int, str]] = []

    def finish_the_window(self, oldest, latest, limit, cursor=""):
        resumed_calls.append((oldest, cursor))
        yield [entry(f"b-{oldest}", oldest + 6)], ""

    monkeypatch.setattr(type(resumed.client), "iter_pages", finish_the_window)

    again = forwarded_ids(resumed)

    assert resumed_calls[0] == (start + 1, "page-2")  # the same window, resumed at the stored cursor
    assert again[0] == f"b-{start + 1}"
    assert "a" not in again  # the first page is never fetched again, let alone pushed again


def test_progress_is_not_recorded_for_a_batch_the_consumer_never_pushed(module, tmp_path, monkeypatch):
    """The SDK pushes each batch inside the body of its `for` loop, so this generator is only
    resumed once the push has returned. Recording before the yield would claim a batch as sent that
    a container killed mid-cycle never actually sent."""
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        slack_like([entry("a", start + 5)], [entry("b", start + 6)]),
    )

    batches = connector.iterate()
    next(batches)  # the first batch is handed out, but nothing pushes it
    batches.close()  # the container dies right here

    progress = stored_progress(tmp_path)
    assert progress.get("pushed_ids", []) == []
    assert progress.get("cursor", "") == ""


def test_a_resumed_window_uses_the_stored_end_not_a_freshly_computed_one(module, tmp_path, monkeypatch):
    """An unfinished window keeps the end it was opened with. Recomputing it from `now - timebuffer`
    would widen the window on every cycle, and a cursor Slack issued for the narrower one would no
    longer match it."""
    start = seconds_ago(3 * 3600)
    frozen_end = start + 100  # far shorter than a sub-window, and clearly in the past
    connector = watermarked(module, tmp_path, start)
    seed_progress(tmp_path, window_start=start + 1, window_end=frozen_end, cursor="page-2")
    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(type(connector.client), "iter_pages", empty_windows(calls))

    list(connector.iterate())

    assert calls[0] == (start + 1, frozen_end, "page-2")
    assert calls[0][1] != start + connector.SUB_WINDOW_SECONDS  # what recomputing would have given


def test_the_checkpoint_commits_the_frozen_end_and_the_next_window_starts_after_it(module, tmp_path, monkeypatch):
    start = seconds_ago(3 * 3600)
    frozen_end = start + 100
    connector = watermarked(module, tmp_path, start)
    seed_progress(tmp_path, window_start=start + 1, window_end=frozen_end, cursor="page-2")
    windows: list[tuple[int, int]] = []

    def drain_the_frozen_window_then_stop(self, oldest, latest, limit, cursor=""):
        windows.append((oldest, latest))
        # the second window is left unfinished, so the cycle ends and the assertions below are
        # about the one commit the frozen window produced
        yield [], "" if len(windows) == 1 else "unfinished"

    monkeypatch.setattr(type(connector.client), "iter_pages", drain_the_frozen_window_then_stop)

    list(connector.iterate())

    assert connector.checkpoint.offset == frozen_end  # the frozen end, not a recomputed one
    assert windows[1][0] == frozen_end + 1


def test_a_fresh_window_stores_both_bounds_on_its_first_progress_write(module, tmp_path, monkeypatch):
    start = seconds_ago(3 * 3600)
    connector = watermarked(module, tmp_path, start)

    def one_page_then_the_budget_runs_out(self, oldest, latest, limit, cursor=""):
        yield [entry("a", oldest + 5)], "page-2"

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page_then_the_budget_runs_out)

    list(connector.iterate())

    assert stored_progress(tmp_path) == {
        "window_start": start + 1,
        "window_end": start + connector.SUB_WINDOW_SECONDS,
        "cursor": "page-2",
        "pushed_ids": ["a"],
        "truncated": False,
    }


def test_an_unfinished_window_stops_the_cycle_instead_of_moving_past_it(module, tmp_path, monkeypatch):
    start = seconds_ago(3 * 3600)
    connector = watermarked(module, tmp_path, start)
    calls: list[int] = []

    def never_finishes(self, oldest, latest, limit, cursor=""):
        calls.append(oldest)
        yield [], "still-more"

    monkeypatch.setattr(type(connector.client), "iter_pages", never_finishes)

    assert list(connector.iterate()) == []

    assert calls == [start + 1]  # the two windows behind it are left for the next cycle
    assert connector.checkpoint.offset == start
    assert stored_progress(tmp_path)["cursor"] == "still-more"


def test_an_excluded_action_is_not_forwarded(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    page = [entry("a", start + 5), entry("b", start + 6)]
    page[0]["action"] = "file_downloaded"
    page[1]["action"] = "user_login"

    connector = watermarked(module, tmp_path, start, excluded_actions=["file_downloaded"])

    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter(
            [([e for e in page if oldest <= e["date_create"] <= latest], "")]
        ),
    )

    pushed: list[str] = []
    for events, _ in connector.iterate():
        pushed += [orjson.loads(event)["id"] for event in events]

    assert pushed == ["b"]


def test_a_page_of_only_excluded_actions_still_drains_its_window(module, tmp_path, monkeypatch):
    """The window must still commit, or the watermark would stall on a filtered-out action."""
    start = seconds_ago(2 * 3600)
    page = [entry("a", start + 5)]
    page[0]["action"] = "file_downloaded"

    connector = watermarked(module, tmp_path, start, excluded_actions=["file_downloaded"])

    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter(
            [([e for e in page if oldest <= e["date_create"] <= latest], "")]
        ),
    )

    assert list(connector.iterate()) == []
    assert connector.checkpoint.offset > start


def test_an_entry_repeated_inside_one_page_is_forwarded_once(module, tmp_path, monkeypatch):
    """The ledger is consulted once per page, so a repeat inside one page would slip past it.

    Slack has never been observed doing this - the duplicates in our sample corpus turned out to be
    a capture artifact. This guards the case rather than a measured behaviour.
    """
    start = seconds_ago(2 * 3600)
    repeated = entry("a", start + 5)
    page = [repeated, entry("b", start + 6), dict(repeated)]

    connector = watermarked(module, tmp_path, start)

    def one_page(self, oldest, latest, limit, cursor=""):
        yield [event for event in page if oldest <= event["date_create"] <= latest], ""

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page)

    pushed: list[str] = []
    for events, _ in connector.iterate():
        pushed += [orjson.loads(event)["id"] for event in events]

    assert pushed == ["a", "b"]


def test_events_already_pushed_in_an_interrupted_window_are_not_pushed_again(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    first_page = [entry("a", start + 5), entry("b", start + 6)]
    second_page = [entry("c", start + 7)]

    connector = watermarked(module, tmp_path, start)

    def one_page_then_boom(self, oldest, latest, limit, cursor=""):
        yield [event for event in first_page if oldest <= event["date_create"] <= latest], "cursor-1"
        raise SlackAuditLogsError("boom")

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page_then_boom)

    pushed: list[str] = []
    with pytest.raises(SlackAuditLogsError):
        for events, _ in connector.iterate():
            pushed += [orjson.loads(event)["id"] for event in events]

    assert pushed == ["a", "b"]
    assert connector.checkpoint.offset == start  # the window never drained, so nothing was committed

    # the container restarts on the same data path and finishes the very same window
    resumed = SlackAuditLogsConnector(module=module, data_path=tmp_path)
    resumed.configuration = dict(CONFIGURATION)
    monkeypatch.setattr(type(resumed.client), "iter_pages", slack_like(first_page, second_page))

    assert forwarded_ids(resumed) == ["c"]


def test_the_ledger_survives_a_window_whose_far_end_has_moved(module, tmp_path, monkeypatch):
    """The window at the head of the stream ends at `now - timebuffer`, so its end moves between
    cycles while its start stays pinned to the watermark. Progress is keyed on the start for
    exactly that reason; keying it on the end would drop it on every restart. Here the end is
    moved through the timebuffer rather than the clock, to keep the test deterministic."""
    start = seconds_ago(1800)
    first_page = [entry("a", start + 5)]
    second_page = [entry("b", start + 6)]

    connector = watermarked(module, tmp_path, start, timebuffer=60)

    def one_page_then_boom(self, oldest, latest, limit, cursor=""):
        yield first_page, "cursor-1"
        raise SlackAuditLogsError("boom")

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page_then_boom)

    with pytest.raises(SlackAuditLogsError):
        list(connector.iterate())

    # the same window, one second wider at its far end, as a later cycle would find it
    resumed = watermarked(module, tmp_path, start, timebuffer=59)
    monkeypatch.setattr(type(resumed.client), "iter_pages", slack_like(first_page, second_page))

    assert forwarded_ids(resumed) == ["b"]


def test_a_rejected_stored_cursor_re_reads_the_window_from_its_start_without_re_pushing(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    seed_progress(
        tmp_path,
        window_start=start + 1,
        window_end=start + 3600,
        cursor="stale-cursor",
        pushed_ids=[f"a-{start + 1}"],
    )
    cursors: list[str] = []

    def reject_the_stored_cursor(self, oldest, latest, limit, cursor=""):
        cursors.append(cursor)
        if cursor:
            raise SlackAuditLogsError("invalid_cursor")
        # ids carry their window, so a re-push is distinguishable from a later window's events
        yield [entry(f"a-{oldest}", oldest + 5), entry(f"b-{oldest}", oldest + 6)], ""

    monkeypatch.setattr(type(connector.client), "iter_pages", reject_the_stored_cursor)

    again = forwarded_ids(connector)

    assert cursors[:2] == ["stale-cursor", ""]  # rejected, then read again from the window's start
    assert f"a-{start + 1}" not in again  # an earlier cycle already pushed it; the ledger holds it back
    assert f"b-{start + 1}" in again  # the rest of the window still arrives
    assert connector.checkpoint.offset > start  # and the window commits normally


def test_the_stored_cursor_is_dropped_once_and_then_the_error_propagates(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    seed_progress(tmp_path, window_start=start + 1, window_end=start + 3600, cursor="stale-cursor")
    attempts: list[str] = []

    def always_fails(self, oldest, latest, limit, cursor=""):
        attempts.append(cursor)
        raise SlackAuditLogsError("nope")
        yield  # makes this a generator function, like the real iter_pages

    monkeypatch.setattr(type(connector.client), "iter_pages", always_fails)

    with pytest.raises(SlackAuditLogsError):
        list(connector.iterate())

    assert attempts == ["stale-cursor", ""]  # one retry without the cursor, then it propagates
    assert connector.checkpoint.offset == start
    assert stored_progress(tmp_path)["cursor"] == ""  # the stale cursor is not offered again


def test_a_failure_after_a_page_advanced_the_cursor_is_not_read_as_a_rejected_cursor(module, tmp_path, monkeypatch):
    """A 5xx in the middle of a window is not the opening cursor's fault. Re-reading would spend the
    window's requests again to re-deliver what this cycle just pushed."""
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    seed_progress(tmp_path, window_start=start + 1, window_end=start + 3600, cursor="page-2")
    attempts: list[str] = []

    def fail_once_a_page_has_landed(self, oldest, latest, limit, cursor=""):
        attempts.append(cursor)
        yield [entry(f"a-{oldest}", oldest + 5)], "page-3"
        raise SlackAuditLogsError("HTTP 502")

    monkeypatch.setattr(type(connector.client), "iter_pages", fail_once_a_page_has_landed)

    with pytest.raises(SlackAuditLogsError):
        list(connector.iterate())

    assert attempts == ["page-2"]  # the window is not re-read from its start
    assert stored_progress(tmp_path)["cursor"] == "page-3"  # the cursor this cycle earned survives
    assert not any("rejected the stored cursor" in message for _, message in logged)


def test_a_credential_failure_is_not_retried_as_a_stale_cursor(module, tmp_path, monkeypatch):
    """A rejected token is not a rejected cursor: retrying would spend a request to fail the same
    way, and would log a misleading cursor warning on the way."""
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    seed_progress(tmp_path, window_start=start + 1, window_end=start + 3600, cursor="stale-cursor")
    attempts: list[str] = []

    def reject_the_token(self, oldest, latest, limit, cursor=""):
        attempts.append(cursor)
        raise AuthenticationError("token_revoked")
        yield  # makes this a generator function, like the real iter_pages

    monkeypatch.setattr(type(connector.client), "iter_pages", reject_the_token)

    assert list(connector.iterate()) == []

    assert attempts == ["stale-cursor"]  # tried once, not retried without the cursor
    assert [level for level, _ in logged] == ["critical"]


def test_an_entry_without_a_usable_timestamp_is_forwarded_silently(module, tmp_path, monkeypatch):
    """Under a zero-miss requirement an entry must never disappear quietly. It is forwarded like any
    other and only kept out of the event-lag figure - and deliberately not logged: Slack stamps every
    audit entry, so a warning here would be prose about a case this endpoint does not produce."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    page = [{"id": "bad"}, entry("good", start + 5)]

    monkeypatch.setattr(
        type(connector.client), "iter_pages", lambda self, oldest, latest, limit, cursor="": iter([(page, "")])
    )

    batches = list(connector.iterate())

    events, last_event_date = batches[0]
    assert [orjson.loads(event)["id"] for event in events] == ["bad", "good"]
    # the undated entry cannot contribute a date, so the batch is dated by the one that can
    assert last_event_date == datetime.fromtimestamp(start + 5, tz=UTC).replace(tzinfo=None)
    assert logged == []  # both entries carry an id, and an absent date is not worth a log line
    assert connector.checkpoint.offset > start  # the window still drained


def test_a_page_where_no_entry_carries_a_date_is_forwarded_without_one(module, tmp_path, monkeypatch):
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    page = [{"id": "bad"}, {"id": "worse", "date_create": "not-a-number"}]

    monkeypatch.setattr(
        type(connector.client), "iter_pages", lambda self, oldest, latest, limit, cursor="": iter([(page, "")])
    )

    batches = list(connector.iterate())

    events, last_event_date = batches[0]
    assert [orjson.loads(event)["id"] for event in events] == ["bad", "worse"]
    # None rather than the epoch: a bogus date would report a 56-year lag to the platform
    assert last_event_date is None


def test_the_first_run_starts_one_lookback_window_back(connector, tmp_path):
    fresh = SlackAuditLogsConnector(module=connector.module, data_path=tmp_path)
    fresh.configuration = {"intake_key": "intake-key", "lookback_seconds": 7200}

    expected = int(datetime.now(UTC).timestamp()) - 7200

    assert abs(fresh.checkpoint.offset - expected) <= 5


def test_a_watermark_older_than_a_month_is_not_clamped_forward(connector, tmp_path):
    long_ago = (datetime.now(UTC) - timedelta(days=60)).replace(microsecond=0)
    (tmp_path / "context.json").write_text(orjson.dumps({"most_recent_date_seen": long_ago.isoformat()}).decode())

    resumed = SlackAuditLogsConnector(module=connector.module, data_path=tmp_path)
    resumed.configuration = {"intake_key": "intake-key"}

    assert resumed.checkpoint.offset == int(long_ago.timestamp())


def test_iterate_logs_critical_and_stops_when_slack_rejects_the_credentials(connector, monkeypatch):
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))

    def reject(self, oldest, latest, limit, cursor=""):
        raise AuthenticationError("not_authed")
        yield  # makes `reject` a generator function, like the real iter_pages

    monkeypatch.setattr(type(connector.client), "iter_pages", reject)

    assert list(connector.iterate()) == []
    assert logged[0][0] == "critical"
    assert "not_authed" in logged[0][1]


# --- C1: a forward that did not happen must not be recorded as if it had ------------------------


def sdk_send_chunk(failing: set[int], event_ids_per_chunk: int = 1):
    """Stands in for the SDK's `_send_chunk`. A POST that succeeded always inserts its key, even when
    the intake returns no event ids at all; one that failed logs and leaves the key absent."""

    def _send_chunk(self, batch_api, chunk_index, chunk, collect_ids):
        if chunk_index not in failing:
            collect_ids[chunk_index] = [f"id-{chunk_index}"] * event_ids_per_chunk

    return _send_chunk


def sdk_push(chunks: int):
    """Stands in for the SDK's `push_events_to_intakes`: splits the batch into `chunks` chunks, calls
    `_send_chunk` for each, and returns the ids of the ones that reported."""

    def push_events_to_intakes(self, events, sync=False):
        collect_ids: dict[int, list[str]] = {}
        for index in range(chunks):
            try:
                self._send_chunk("https://intake.test/batch", index, events, collect_ids)
            except Exception:  # the real SDK runs these on an executor, and
                pass  # `wait_futures` discards whatever a worker raises

        return [event_id for index in sorted(collect_ids) for event_id in collect_ids[index]]

    return push_events_to_intakes


def test_a_chunk_whose_post_did_not_succeed_is_counted(connector, monkeypatch):
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing={0}))
    collect_ids: dict[int, list[str]] = {}

    connector._send_chunk("https://intake.test/batch", 0, ['{"id": "a"}'], collect_ids)

    assert connector._failed_chunks == 1


def test_a_chunk_that_landed_is_not_counted(connector, monkeypatch):
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing=set()))
    collect_ids: dict[int, list[str]] = {}

    connector._send_chunk("https://intake.test/batch", 0, ['{"id": "a"}'], collect_ids)

    assert connector._failed_chunks == 0


def test_a_batch_where_only_some_chunks_landed_raises(connector, monkeypatch):
    """The forbidden outcome this closes: the ids of the chunks that did land come back non-empty, so
    counting ids cannot see the loss. A batch reaches several chunks at CHUNK_BYTES_MAX_SIZE with
    ordinary entry sizes once `limit` is near its ceiling, so this is not an exotic case."""
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing={1}))
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=2))

    with pytest.raises(SlackAuditLogsError, match="1 of this batch's chunks"):
        connector.push_events_to_intakes(['{"id": "a"}', '{"id": "b"}'])


def test_a_batch_whose_every_chunk_landed_does_not_raise(connector, monkeypatch):
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing=set()))
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=2))

    assert connector.push_events_to_intakes(['{"id": "a"}']) == ["id-0", "id-1"]


def test_a_success_that_returned_no_event_ids_does_not_raise(connector, monkeypatch):
    """A 200 carrying no `event_ids` is a delivered batch. Treating it as a failure would leave the
    window uncommitted and re-push the same batch every cycle, for ever."""
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing=set(), event_ids_per_chunk=0))
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=2))

    assert connector.push_events_to_intakes(['{"id": "a"}']) == []


def test_a_batch_that_produced_no_chunk_at_all_does_not_raise(connector, monkeypatch):
    """Every event above EVENT_BYTES_MAX_SIZE is discarded before chunking, so nothing is sent and
    nothing failed. Raising would stall the window for ever."""
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing=set()))
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=0))

    assert connector.push_events_to_intakes(["x" * (EVENT_BYTES_MAX_SIZE + 1)]) == []


def test_the_failure_count_does_not_carry_over_into_the_next_batch(connector, monkeypatch):
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=1))
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing={0}))

    with pytest.raises(SlackAuditLogsError):
        connector.push_events_to_intakes(['{"id": "a"}'])

    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing=set()))

    assert connector.push_events_to_intakes(['{"id": "b"}']) == ["id-0"]


def test_a_push_that_raises_leaves_the_ledger_and_the_checkpoint_untouched(module, tmp_path, monkeypatch):
    """The whole point of raising: the events are not recorded, the window is not committed, and the
    next cycle reads it again."""
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(type(connector.client), "iter_pages", slack_like([entry("a", start + 5)]))

    batches = connector.iterate()
    next(batches)

    with pytest.raises(SlackAuditLogsError):
        batches.throw(SlackAuditLogsError("the intake accepted none of the 1 events in this batch"))

    assert stored_progress(tmp_path).get("pushed_ids", []) == []
    assert connector.checkpoint.offset == start


# --- I3: the ledger is bounded and ordered ------------------------------------------------------


def test_the_ledger_keeps_the_ids_a_re_read_would_meet_first(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start, limit=2)  # so the bound is 2 x 2 = 4 ids
    # Slack pages newest first, page 1 carries most recent event of the window and its ids are appended first.
    pages = [[entry(f"e{index}", start + 8 - index)] for index in range(1, 8)]

    def seven_pages_then_unfinished(self, oldest, latest, limit, cursor=""):
        for index, page in enumerate(pages, start=1):
            yield page, f"cursor-{index}"

    monkeypatch.setattr(type(connector.client), "iter_pages", seven_pages_then_unfinished)

    list(connector.iterate())

    stored = stored_progress(tmp_path)
    # A re-read restarts at page 1, so the ledger has to hold those ids, not the tail it ends on.
    assert stored["pushed_ids"] == ["e1", "e2", "e3", "e4"]
    assert stored["truncated"] is True


def test_an_untrimmed_ledger_is_not_flagged_as_truncated(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start, limit=500)

    def one_page_then_unfinished(self, oldest, latest, limit, cursor=""):
        yield [entry("b", start + 6), entry("a", start + 5)], "page-2"

    monkeypatch.setattr(type(connector.client), "iter_pages", one_page_then_unfinished)

    list(connector.iterate())

    stored = stored_progress(tmp_path)
    assert stored["pushed_ids"] == ["b", "a"]  # insertion order, not sorted
    assert stored["truncated"] is False


def test_a_stale_cursor_re_read_on_a_trimmed_ledger_warns_that_duplicates_are_possible(module, tmp_path, monkeypatch):
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    seed_progress(
        tmp_path,
        window_start=start + 1,
        window_end=start + 3600,
        cursor="stale-cursor",
        pushed_ids=["a"],
        truncated=True,
    )

    def reject_the_stored_cursor(self, oldest, latest, limit, cursor=""):
        if cursor:
            raise SlackAuditLogsError("invalid_cursor")
        yield [], ""

    monkeypatch.setattr(type(connector.client), "iter_pages", reject_the_stored_cursor)

    list(connector.iterate())

    warnings = [message for level, message in logged if level == "warning"]
    assert any("second time" in message for message in warnings)


# --- I1: the operator-facing numbers are bounded ------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("frequency", 9),  # would hammer Slack's org-wide quota
        ("frequency", 3601),
        ("limit", 0),
        ("limit", 10_000),  # Slack's documented maximum is 9999
        ("ratelimit_per_minute", 0),
        ("ratelimit_per_minute", 51),  # above Slack's Tier 3 allowance
        ("timebuffer", 0),  # would commit `latest = now` and lose late-indexed events
        ("timebuffer", -60),  # would commit into the future
        ("lookback_seconds", 59),
    ],
)
def test_a_configuration_number_outside_its_bounds_is_refused(field, value):
    with pytest.raises(ValidationError):
        SlackAuditLogsConnectorConfiguration(intake_key="intake-key", **{field: value})


def test_the_default_configuration_is_within_its_bounds():
    configuration = SlackAuditLogsConnectorConfiguration(intake_key="intake-key")

    assert (configuration.frequency, configuration.limit) == (60, 1000)
    assert (configuration.ratelimit_per_minute, configuration.timebuffer) == (30, 60)
    assert configuration.lookback_seconds == 3600


# --- M1: a frozen end left ahead of the buffer by a clock step ----------------------------------


def test_a_frozen_end_ahead_of_the_settled_boundary_is_left_alone_this_cycle(module, tmp_path, monkeypatch):
    """A backwards clock step can leave a stored end in the future relative to the buffer. Reading
    to it would commit past the buffer and lose whatever Slack indexes in between."""
    start = seconds_ago(2 * 3600)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    seed_progress(tmp_path, window_start=start + 1, window_end=seconds_ago(-600), cursor="page-2")
    calls: list[tuple[int, int, str]] = []
    monkeypatch.setattr(type(connector.client), "iter_pages", empty_windows(calls))

    assert list(connector.iterate()) == []

    assert calls == []  # nothing was requested at all
    assert connector.checkpoint.offset == start
    assert logged[-1][0] == "warning"
    assert "stepped" in logged[-1][1]


# --- pacing and an unwritable data path ---------------------------------------------------------


def test_next_run_pads_the_cycle_out_to_the_configured_frequency(connector, monkeypatch):
    """The SDK skips its own pause whenever a cycle forwarded events, which on an active org would
    poll flat out at `ratelimit_per_minute` - most of Slack's org-wide Tier 3 budget."""
    slept: list[float] = []
    monkeypatch.setattr(Connector, "next_run", lambda self: None)
    monkeypatch.setattr("slack_modules.connector.time.sleep", slept.append)

    connector.next_run()

    assert len(slept) == 1
    assert slept[0] == pytest.approx(connector.frequency, abs=1)


def test_a_cycle_that_already_took_its_frequency_is_not_padded(connector, monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(Connector, "next_run", lambda self: None)
    monkeypatch.setattr("slack_modules.connector.time.sleep", slept.append)
    # a cycle that consumed the whole frequency and then some
    clock = iter([1000.0, 1000.0 + connector.frequency + 5])
    monkeypatch.setattr("slack_modules.connector.time.time", lambda: next(clock))

    connector.next_run()

    assert slept == []


def failing_dump_after(successes: int):
    """A `PersistentJSON.dump` that works `successes` times and then fails, the way an unwritable data
    path does. PersistentJSON dumps on every context exit, even a read-only one, so inside `iterate()`
    the write order is: 1. reading the watermark, 2. `_resume`, 3. `_remember` after a batch was
    pushed. Only that last one is the re-ingestion loop; all three have to reach the handler."""
    state = {"calls": 0}

    def dump(self):
        state["calls"] += 1
        if state["calls"] > successes:
            raise OSError("Read-only file system")

    return dump


@pytest.mark.parametrize(
    "successes,ordering",
    [(0, "reading the watermark"), (1, "_resume"), (2, "_remember, after the events were pushed")],
)
def test_an_unwritable_data_path_logs_critical_and_re_raises(module, tmp_path, monkeypatch, successes, ordering):
    """In the image `data_path` falls back to /symphony_data, which nothing creates. Unwritable, the
    connector must say so itself rather than leaving the SDK to log one line per cycle while it
    re-sends the same window."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    monkeypatch.setattr(type(connector.client), "iter_pages", slack_like([entry("a", start + 5)]))
    monkeypatch.setattr(PersistentJSON, "dump", failing_dump_after(successes))

    with pytest.raises(OSError):
        list(connector.iterate())

    assert logged[-1][0] == "critical", f"no critical log for the {ordering} ordering"
    assert "writable" in logged[-1][1]


# --- N1: an entry without an id is never suppressed ---------------------------------------------


def test_two_byte_identical_entries_without_an_id_both_reach_the_intake(module, tmp_path, monkeypatch):
    """The whole point of the round: two entries with no id can be byte-identical and still be two
    distinct events. Anything that derives a key from their content - a hash, or the literal "None" -
    makes the second look like a re-delivery and drops it silently."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    twin = {"date_create": start + 5, "action": "user_login"}
    # Two on one page and a third on the next, because the ledger is consulted once per page: a
    # content-derived key collides across pages, which is where the drop happened.
    monkeypatch.setattr(type(connector.client), "iter_pages", slack_like([dict(twin), dict(twin)], [dict(twin)]))

    forwarded = [orjson.loads(event) for events, _ in connector.iterate() for event in events]

    assert len(forwarded) == 3
    assert {event["action"] for event in forwarded} == {"user_login"}


def test_an_entry_without_an_id_is_not_written_into_the_ledger(module, tmp_path, monkeypatch):
    """The ledger holds real Slack ids only, which is what keeps its `2 x limit` bound meaningful."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    page = [entry("has-id", start + 5), {"date_create": start + 6, "action": "user_login"}]
    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter([(page, "page-2")]),
    )

    list(connector.iterate())

    assert stored_progress(tmp_path)["pushed_ids"] == ["has-id"]


def test_forwarding_entries_without_an_id_is_reported_with_a_count(module, tmp_path, monkeypatch):
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    page = [entry("has-id", start + 5), {"id": None, "date_create": start + 6, "action": "user_login"}]
    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter([(page, "")]),
    )

    list(connector.iterate())

    warnings = [message for level, message in logged if level == "warning"]
    assert any("1 of 2 entries with no id" in message for message in warnings)
    assert any("twice" in message for message in warnings)


def test_a_resume_suppresses_the_identified_entries_and_re_delivers_the_id_less_one(module, tmp_path, monkeypatch):
    """The trade, stated as a test: the entry with an id is held back on a re-read, the one without is
    delivered again. A bounded duplicate, announced in the logs, instead of a silent drop."""
    start = seconds_ago(1800)
    page = [entry("a", start + 5), {"date_create": start + 6, "action": "user_login"}]

    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter([(page, "page-2")]),
    )

    first = [orjson.loads(event) for events, _ in connector.iterate() for event in events]
    assert len(first) == 2  # unfinished window, both entries forwarded

    resumed = SlackAuditLogsConnector(module=module, data_path=tmp_path)
    resumed.configuration = dict(CONFIGURATION)
    monkeypatch.setattr(resumed, "log", lambda message, level="info", **kwargs: None)
    monkeypatch.setattr(
        type(resumed.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter([(page, "")]),
    )

    again = [orjson.loads(event) for events, _ in resumed.iterate() for event in events]

    assert len(again) == 1
    assert "id" not in again[0]  # the identified entry was suppressed, this one could not be


# --- round 7: the two remaining losses, made loud ------------------------------------------------


def test_a_chunk_whose_worker_raised_is_still_counted(connector, monkeypatch):
    """`super()._send_chunk` does not always return: its own failure handler calls
    `self.log(level="error")`, a synchronous POST to the platform API which re-raises when that API is
    unreachable too - the same outage that broke the intake POST. Counting only on a normal return
    missed exactly that, and the escaping exception is swallowed by the SDK's `wait_futures`."""

    def the_platform_api_is_down_as_well(self, batch_api, chunk_index, chunk, collect_ids):
        raise RuntimeError("failed to log the failure")

    monkeypatch.setattr(Connector, "_send_chunk", the_platform_api_is_down_as_well)
    collect_ids: dict[int, list[str]] = {}

    with pytest.raises(RuntimeError):
        connector._send_chunk("https://intake.test/batch", 0, ['{"id": "a"}'], collect_ids)

    assert connector._failed_chunks == 1


def test_a_batch_where_a_worker_raised_is_reported_as_a_failure(connector, monkeypatch):
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)

    def one_chunk_lands_the_other_worker_raises(self, batch_api, chunk_index, chunk, collect_ids):
        if chunk_index == 1:
            raise RuntimeError("failed to log the failure")
        collect_ids[chunk_index] = [f"id-{chunk_index}"]

    monkeypatch.setattr(Connector, "_send_chunk", one_chunk_lands_the_other_worker_raises)
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=2))

    with pytest.raises(SlackAuditLogsError, match="1 of this batch's chunks"):
        connector.push_events_to_intakes(['{"id": "a"}', '{"id": "b"}'])


def test_an_event_too_large_for_the_platform_is_named_in_a_critical_log(module, tmp_path, monkeypatch):
    """It is discarded before any chunk exists, so no failure is countable and holding the window back
    would stall it for ever. Naming it is the only honest handling left."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    huge = entry("huge", start + 5) | {"payload": "x" * (EVENT_BYTES_MAX_SIZE + 100)}
    page = [huge, entry("small", start + 6)]
    monkeypatch.setattr(
        type(connector.client),
        "iter_pages",
        lambda self, oldest, latest, limit, cursor="": iter([(page, "")]),
    )

    forwarded = [orjson.loads(event)["id"] for events, _ in connector.iterate() for event in events]

    criticals = [message for level, message in logged if level == "critical"]
    assert len(criticals) == 1
    assert "id huge" in criticals[0]
    assert "bytes" in criticals[0]
    assert str(EVENT_BYTES_MAX_SIZE) in criticals[0]
    assert "small" not in criticals[0]
    assert forwarded == ["huge", "small"]  # the rest of the batch is untouched, and so is the window
    assert connector.checkpoint.offset > start


def test_a_failed_forward_warns_that_the_page_will_be_read_again(connector, monkeypatch):
    """A 2xx whose body cannot be parsed leaves the chunk key unset too, so it is indistinguishable
    from a real failure here. The retry stays, but it stops being invisible."""
    logged: list[tuple] = []
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: logged.append((level, message)))
    monkeypatch.setattr(Connector, "_send_chunk", sdk_send_chunk(failing={0}))
    monkeypatch.setattr(Connector, "push_events_to_intakes", sdk_push(chunks=1))

    with pytest.raises(SlackAuditLogsError):
        connector.push_events_to_intakes(['{"id": "a"}'])

    warnings = [message for level, message in logged if level == "warning"]
    assert len(warnings) == 1
    assert "next cycle" in warnings[0]
    assert "pending.json" in warnings[0]


def test_the_stored_cursor_still_re_fetches_the_page_being_forwarded(module, tmp_path, monkeypatch):
    """What makes that warning true: pending.json is written only after a batch has been forwarded, so
    while a forward is in flight the stored cursor is the one that re-fetches that same page - never
    the page's own next_cursor, which would skip it."""
    start = seconds_ago(1800)
    connector = watermarked(module, tmp_path, start)
    monkeypatch.setattr(connector, "log", lambda message, level="info", **kwargs: None)
    monkeypatch.setattr(
        type(connector.client), "iter_pages", slack_like([entry("a", start + 5)], [entry("b", start + 6)])
    )

    batches = connector.iterate()

    next(batches)
    # page 1 in flight: nothing recorded yet, so a failure reopens the window from its start
    assert stored_progress(tmp_path).get("cursor", "") == ""
    next(batches)
    # page 2 in flight: the stored cursor is the one page 1 handed back, which re-fetches page 2
    assert stored_progress(tmp_path)["cursor"] == "cursor-1"
