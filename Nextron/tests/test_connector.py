"""Regression tests for the THOR Cloud connector's scan-completion gating.

The connector must only pull (and mark as processed) scans that have actually
finished, detected by `thor.json` appearing in the scan's `available_logs`. A
scan seen while still running must be left un-processed so a later poll re-checks
it once it has finished.
"""

from datetime import datetime, timedelta, timezone

import pytest
import requests

from thor_cloud_modules import client
from thor_cloud_modules.connector import ThorCloudConnector, ThorCloudConnectorConfiguration
from thor_cloud_modules.models import ThorCloudModuleConfiguration


@pytest.fixture
def connector(tmp_path, monkeypatch):
    conn = ThorCloudConnector(data_path=tmp_path)
    # api_key is a module-level secret, read via self.module.configuration.
    conn.module._configuration = ThorCloudModuleConfiguration(api_key="k")
    conn.configuration = ThorCloudConnectorConfiguration(
        intake_key="intake-123",
        product="thor_cloud_lite",
        days_back=7,
        polling_interval=1,
    )
    # Silence logging plumbing that needs a full runtime.
    monkeypatch.setattr(conn, "log", lambda *a, **k: None)
    monkeypatch.setattr(conn, "log_exception", lambda *a, **k: None)
    # Run exactly one poll iteration, then stop the loop.
    monkeypatch.setattr(conn, "_wait", lambda *_a, **_k: conn.stop())
    return conn


def _accepting_push(pushed: list[str]):
    """Fake push that accepts every event, returning one event ID per event like the SDK."""

    def push(events):
        pushed.extend(events)
        return [f"id-{i}" for i in range(len(events))]

    return push


def _run_once(connector, monkeypatch, scans, logs_by_scan):
    pushed: list[str] = []
    monkeypatch.setattr(connector, "push_events_to_intakes", _accepting_push(pushed))
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: scans)

    fetched: list[str] = []

    def fake_fetch_logs(base_url, headers, scan_id, log_type="thor.json"):
        fetched.append(scan_id)
        return logs_by_scan.get(scan_id, [])

    monkeypatch.setattr(client, "fetch_scan_logs", fake_fetch_logs)

    connector.run()
    return pushed, fetched


def test_running_scan_is_not_pulled_or_marked_processed(connector, monkeypatch):
    """A scan without thor.json yet is skipped and NOT persisted as processed."""
    scans = [{"id": "running-1", "creation_date": 4102444800, "available_logs": [], "status": "running"}]

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan={})

    assert fetched == []  # never called the log endpoint for an unfinished scan
    assert pushed == []
    assert connector._load_processed() == {}  # not remembered -> will be re-checked


def test_failed_scan_with_logs_is_pulled(connector, monkeypatch):
    """A failed scan is terminal -> pull its results if a thor.json was produced."""
    scans = [{"id": "failed-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "failed"}]
    logs = {"failed-1": [{"time": "2026-06-23T07:17:48Z", "message": "partial"}]}

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan=logs)

    assert fetched == ["failed-1"]
    assert len(pushed) == 1
    assert "failed-1" in connector._load_processed()


def test_terminal_scan_without_logs_is_marked_processed_without_pulling(connector, monkeypatch):
    """A terminal scan that produced no thor.json -> nothing to fetch, mark processed."""
    scans = [{"id": "failed-2", "creation_date": 4102444800, "available_logs": [], "status": "failed"}]

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan={})

    assert fetched == []
    assert pushed == []
    assert "failed-2" in connector._load_processed()  # remembered -> not re-checked


def test_successful_scan_is_pulled_and_marked_processed(connector, monkeypatch):
    scans = [{"id": "done-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]
    logs = {"done-1": [{"time": "2026-06-23T07:17:48Z", "message": "hit"}]}

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan=logs)

    assert fetched == ["done-1"]
    assert len(pushed) == 1
    assert "done-1" in connector._load_processed()


def test_empty_api_key_is_reported_and_iteration_skipped(connector, monkeypatch):
    """A blank api_key short-circuits the poll before any request is made."""
    connector.module._configuration = ThorCloudModuleConfiguration(api_key="")

    called = {"fetch": False}
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: called.__setitem__("fetch", True) or [])

    connector.run()  # fixture's sleep() stops the loop after one iteration

    assert called["fetch"] is False  # never reached the API call


def test_fetch_scans_request_error_is_handled_and_retried(connector, monkeypatch):
    """A network error while listing scans is caught; the loop sleeps and retries."""

    def boom(*a, **k):
        raise requests.RequestException("boom")

    monkeypatch.setattr(client, "fetch_scans", boom)

    connector.run()  # inner except sleeps -> fixture stops the loop

    assert connector._load_processed() == {}  # nothing forwarded/persisted


def test_fetch_logs_request_error_does_not_mark_scan_processed(connector, monkeypatch):
    """If pulling a terminal scan's logs fails, it must NOT be marked processed."""
    scans = [{"id": "err-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: scans)

    def boom(*a, **k):
        raise requests.RequestException("logs down")

    monkeypatch.setattr(client, "fetch_scan_logs", boom)
    pushed: list[str] = []
    monkeypatch.setattr(connector, "push_events_to_intakes", _accepting_push(pushed))

    connector.run()

    assert pushed == []
    assert connector._load_processed() == {}  # retried on the next run


def test_unexpected_error_is_caught_by_outer_handler(connector, monkeypatch):
    """A non-request exception is swallowed and delayed before the loop retries."""

    def kaboom(*a, **k):
        raise ValueError("unexpected")

    monkeypatch.setattr(client, "fetch_scans", kaboom)
    connector.run()  # must return (not loop forever) and not raise

    assert connector._load_processed() == {}


def test_stale_processed_scans_are_pruned_without_new_scans(connector, monkeypatch):
    connector._save_processed({"stale": 0.0, "undated": None})

    _run_once(connector, monkeypatch, [], logs_by_scan={})

    assert connector._load_processed() == {"undated": None}


def test_terminal_scan_without_creation_date_remains_processed(connector, monkeypatch):
    scan = {"id": "undated-1", "available_logs": [], "status": "failed"}

    _run_once(connector, monkeypatch, [scan], logs_by_scan={})
    assert connector._load_processed() == {"undated-1": None}

    connector._stop_event.clear()
    pushed, fetched = _run_once(connector, monkeypatch, [scan], logs_by_scan={})

    assert pushed == []
    assert fetched == []
    assert connector._load_processed() == {"undated-1": None}


def test_running_scan_is_rechecked_after_it_finishes(connector, monkeypatch):
    """The core bug: a scan seen while running must be pulled once it completes."""
    scan_id = "late-1"

    # Poll 1: scan is still running -> skipped, not remembered.
    running = [{"id": scan_id, "creation_date": 4102444800, "available_logs": [], "status": "running"}]
    _run_once(connector, monkeypatch, running, logs_by_scan={})
    assert connector._load_processed() == {}

    # Re-arm the loop for a second single iteration (clear the stop flag set above).
    connector._stop_event.clear()
    monkeypatch.setattr(connector, "_wait", lambda *_a, **_k: connector.stop())

    # Poll 2: same scan has finished -> now pulled and marked processed.
    finished = [{"id": scan_id, "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]
    logs = {scan_id: [{"time": "2026-06-23T07:17:48Z", "message": "hit"}]}
    pushed, fetched = _run_once(connector, monkeypatch, finished, logs_by_scan=logs)

    assert fetched == [scan_id]
    assert len(pushed) == 1
    assert scan_id in connector._load_processed()


def test_partially_delivered_scan_is_not_marked_processed(connector, monkeypatch):
    """The SDK swallows delivery errors and returns fewer event IDs: the scan must be retried."""
    scans = [{"id": "lost-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]
    logs = {"lost-1": [{"message": "a"}, {"message": "b"}]}
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: scans)
    monkeypatch.setattr(client, "fetch_scan_logs", lambda *a, **k: logs["lost-1"])
    monkeypatch.setattr(connector, "push_events_to_intakes", lambda events: ["only-one"])

    connector.run()

    assert connector._load_processed() == {}


def test_failed_scan_does_not_block_other_scans(connector, monkeypatch):
    """Each scan is pushed and persisted on its own, so one failure doesn't affect the others."""
    scans = [
        {"id": "ok-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"},
        {"id": "lost-2", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"},
    ]
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: scans)
    monkeypatch.setattr(client, "fetch_scan_logs", lambda base_url, headers, scan_id, **k: [{"scan": scan_id}])
    pushes: list[list[str]] = []

    def push(events):
        pushes.append(events)
        return [] if "lost-2" in events[0] else ["id"] * len(events)

    monkeypatch.setattr(connector, "push_events_to_intakes", push)

    connector.run()

    assert len(pushes) == 2  # one push per scan, not one batch for the whole poll
    assert set(connector._load_processed()) == {"ok-1"}


def test_scan_with_encrypted_logs_is_skipped_without_download(connector, monkeypatch):
    scans = [
        {
            "id": "enc-1",
            "creation_date": 4102444800,
            "available_logs": ["thor.json"],
            "status": "successful",
            "logs_encrypted": True,
        }
    ]

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan={})

    assert fetched == []
    assert pushed == []
    assert "enc-1" in connector._load_processed()


def test_scan_with_empty_log_is_marked_processed(connector, monkeypatch):
    scans = [{"id": "empty-1", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]

    pushed, fetched = _run_once(connector, monkeypatch, scans, logs_by_scan={"empty-1": []})

    assert fetched == ["empty-1"]
    assert pushed == []
    assert "empty-1" in connector._load_processed()


def test_stop_interrupts_the_scan_loop(connector, monkeypatch):
    """Once stop() is called, remaining scans are left for the next start."""
    scans = [
        {"id": f"s-{i}", "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}
        for i in range(3)
    ]
    monkeypatch.setattr(client, "fetch_scans", lambda *a, **k: scans)
    monkeypatch.setattr(client, "fetch_scan_logs", lambda *a, **k: [{"m": 1}])

    def push_then_stop(events):
        connector.stop()
        return ["id"] * len(events)

    monkeypatch.setattr(connector, "push_events_to_intakes", push_then_stop)

    connector.run()

    assert set(connector._load_processed()) == {"s-0"}


def test_wait_returns_immediately_when_stopped(tmp_path):
    conn = ThorCloudConnector(data_path=tmp_path)
    conn._stop_event.set()

    conn._wait(3600)  # would hang the test if it ignored the stop event


def _poll(connector, monkeypatch, days_back, scans):
    """Run one poll with the given Days Back and return the IDs of the forwarded scans."""
    connector._stop_event.clear()
    connector.configuration.days_back = days_back
    monkeypatch.setattr(connector, "_wait", lambda *_a, **_k: connector.stop())
    pushed, fetched = _run_once(connector, monkeypatch, scans, {s["id"]: [{"scan": s["id"]}] for s in scans})
    return fetched


def _finished_scan(scan_id, days_ago):
    created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).timestamp()
    return {"id": scan_id, "creation_date": int(created), "available_logs": ["thor.json"], "status": "successful"}


def test_raising_days_back_does_not_resend_pruned_scans(connector, monkeypatch):
    seen = _finished_scan("seen-5d", days_ago=5)
    never_seen = _finished_scan("never-seen-20d", days_ago=20)

    # Poll 1: the scan is inside the 7-day window and is forwarded.
    assert _poll(connector, monkeypatch, 7, [seen]) == ["seen-5d"]

    # Poll 2: the window shrinks to 3 days, so the scan's entry is pruned.
    assert _poll(connector, monkeypatch, 3, []) == []
    assert "seen-5d" not in connector._load_processed()

    # Poll 3: the window grows to 30 days. The pruned scan must not be sent again,
    # but a scan that was never inside any window is backfilled.
    assert _poll(connector, monkeypatch, 30, [seen, never_seen]) == ["never-seen-20d"]


def test_pruned_range_survives_a_restart(connector, monkeypatch):
    seen = _finished_scan("seen-5d", days_ago=5)
    _poll(connector, monkeypatch, 7, [seen])
    _poll(connector, monkeypatch, 3, [])

    restarted = ThorCloudConnector(data_path=connector.data_path)
    restarted.module._configuration = connector.module._configuration
    restarted.configuration = connector.configuration
    monkeypatch.setattr(restarted, "log", lambda *a, **k: None)
    monkeypatch.setattr(restarted, "log_exception", lambda *a, **k: None)

    assert _poll(restarted, monkeypatch, 30, [seen]) == []


def test_undated_scans_are_not_affected_by_the_pruned_range(connector, monkeypatch):
    connector._save_pruned_range(covered_since=0.0, pruned_until=4102444800.0)
    undated = {"id": "undated-2", "available_logs": ["thor.json"], "status": "successful"}

    assert _poll(connector, monkeypatch, 7, [undated]) == ["undated-2"]
