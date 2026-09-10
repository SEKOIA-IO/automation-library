"""Regression tests for the THOR Cloud connector's scan-completion gating.

The connector must only pull (and mark as processed) scans that have actually
finished, detected by `thor.json` appearing in the scan's `available_logs`. A
scan seen while still running must be left un-processed so a later poll re-checks
it once it has finished.
"""

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
    monkeypatch.setattr("thor_cloud_modules.connector.time.sleep", lambda *_a, **_k: conn.stop())
    return conn


def _run_once(connector, monkeypatch, scans, logs_by_scan):
    pushed: list[str] = []
    monkeypatch.setattr(connector, "push_events_to_intakes", lambda events: pushed.extend(events))
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
    monkeypatch.setattr(connector, "push_events_to_intakes", lambda events: pushed.extend(events))

    connector.run()

    assert pushed == []
    assert connector._load_processed() == {}  # retried on the next run


def test_unexpected_error_is_caught_by_outer_handler(connector, monkeypatch):
    """A non-request exception is swallowed by the outer handler (loop stays alive)."""
    def kaboom(*a, **k):
        raise ValueError("unexpected")

    monkeypatch.setattr(client, "fetch_scans", kaboom)
    # The outer handler has no sleep(), so stop the loop from log_exception instead.
    monkeypatch.setattr(connector, "log_exception", lambda *a, **k: connector.stop())

    connector.run()  # must return (not loop forever) and not raise

    assert connector._load_processed() == {}


def test_running_scan_is_rechecked_after_it_finishes(connector, monkeypatch):
    """The core bug: a scan seen while running must be pulled once it completes."""
    scan_id = "late-1"

    # Poll 1: scan is still running -> skipped, not remembered.
    running = [{"id": scan_id, "creation_date": 4102444800, "available_logs": [], "status": "running"}]
    _run_once(connector, monkeypatch, running, logs_by_scan={})
    assert connector._load_processed() == {}

    # Re-arm the loop for a second single iteration (clear the stop flag set above).
    connector._stop_event.clear()
    monkeypatch.setattr("thor_cloud_modules.connector.time.sleep", lambda *_a, **_k: connector.stop())

    # Poll 2: same scan has finished -> now pulled and marked processed.
    finished = [{"id": scan_id, "creation_date": 4102444800, "available_logs": ["thor.json"], "status": "successful"}]
    logs = {scan_id: [{"time": "2026-06-23T07:17:48Z", "message": "hit"}]}
    pushed, fetched = _run_once(connector, monkeypatch, finished, logs_by_scan=logs)

    assert fetched == [scan_id]
    assert len(pushed) == 1
    assert scan_id in connector._load_processed()
