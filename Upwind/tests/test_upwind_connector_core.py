from datetime import UTC, datetime

import pytest

import upwind.upwind_detections_connector as connector_module
from upwind import UpwindConnectorConfig
from upwind.upwind_detections_connector import OAuthTokenProvider, UpwindDetectionsConnector


class OffsetStore:
    def __init__(self, offset: datetime) -> None:
        self.offset = offset


class FakeContext:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data if data is not None else {}

    def __enter__(self) -> dict:
        return self.data

    def __exit__(self, *args: object) -> bool:
        return False


def build_connector(
    offset: datetime, *, batch_size: int = 2, boundary_ids: list[str] | None = None
) -> UpwindDetectionsConnector:
    connector = object.__new__(UpwindDetectionsConnector)
    connector.last_detection_date = OffsetStore(offset)
    connector._context = FakeContext(
        {"boundary_detection_ids": sorted(boundary_ids)} if boundary_ids is not None else {}
    )
    connector.configuration = UpwindConnectorConfig(
        frequency=60,
        intake_key="test-key",
        batch_size=batch_size,
    )
    connector._oauth_provider = OAuthTokenProvider()
    return connector


def test_next_batch_batches_new_detections_and_updates_checkpoint() -> None:
    since = datetime(2026, 7, 1, tzinfo=UTC)
    connector = build_connector(since, batch_size=2)

    detections = [
        {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
        {"category": "missing-date"},
        {"id": "evt-2", "first_seen_time": "2026-07-03T10:00:00Z"},
        {"id": "evt-3", "last_seen_time": "2026-07-03T10:05:00Z"},
    ]

    calls: list[datetime] = []

    def fake_fetch_detections(*, since: datetime) -> list[dict[str, str]]:
        assert since == datetime(2026, 7, 1, tzinfo=UTC)
        calls.append(since)
        return detections

    pushed_payloads: list[list[str]] = []

    def fake_push_events_to_intakes(outgoing: list[str]) -> list[str]:
        pushed_payloads.append(outgoing)
        return outgoing

    connector.fetch_detections = fake_fetch_detections
    connector.push_events_to_intakes = fake_push_events_to_intakes

    sent = UpwindDetectionsConnector.next_batch(connector)

    # The detection without a parseable timestamp is skipped.
    assert sent == 3
    assert len(calls) == 1
    assert len(pushed_payloads) == 2
    assert len(pushed_payloads[0]) == 2
    assert len(pushed_payloads[1]) == 1
    assert connector.last_detection_date.offset == datetime(2026, 7, 3, 10, 5, tzinfo=UTC)
    # Only the detection at the new watermark is retained for boundary dedup.
    assert connector._context.data["boundary_detection_ids"] == ["evt-3"]


def test_next_batch_skips_detections_at_or_before_checkpoint() -> None:
    since = datetime(2026, 7, 2, 8, 30, tzinfo=UTC)
    connector = build_connector(since, boundary_ids=["evt-1"])

    def fake_fetch_detections(*, since: datetime) -> list[dict[str, str]]:
        return [
            {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
            {"id": "evt-2", "last_seen_time": "2026-07-01T00:00:00Z"},
        ]

    def fake_push_events_to_intakes(outgoing: list[str]) -> list[str]:
        raise AssertionError("push_events_to_intakes should not be called")

    connector.fetch_detections = fake_fetch_detections
    connector.push_events_to_intakes = fake_push_events_to_intakes

    sent = UpwindDetectionsConnector.next_batch(connector)

    assert sent == 0
    assert connector.last_detection_date.offset == since


def test_next_batch_forwards_new_detection_at_checkpoint_boundary() -> None:
    since = datetime(2026, 7, 2, 8, 30, tzinfo=UTC)
    connector = build_connector(since, boundary_ids=["evt-1"])

    def fake_fetch_detections(*, since: datetime) -> list[dict[str, str]]:
        return [
            {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
            {"id": "evt-2", "last_seen_time": "2026-07-02T08:30:00Z"},
        ]

    pushed: list[str] = []

    def fake_push_events_to_intakes(outgoing: list[str]) -> list[str]:
        pushed.extend(outgoing)
        return outgoing

    connector.fetch_detections = fake_fetch_detections
    connector.push_events_to_intakes = fake_push_events_to_intakes

    sent = UpwindDetectionsConnector.next_batch(connector)

    # evt-1 is deduped by boundary id, evt-2 is new at the same timestamp.
    assert sent == 1
    assert connector.last_detection_date.offset == since
    assert connector._context.data["boundary_detection_ids"] == ["evt-1", "evt-2"]


class DummyStopEvent:
    def __init__(self) -> None:
        self._is_set = False

    def is_set(self) -> bool:
        return self._is_set

    def set(self) -> None:
        self._is_set = True


def test_run_sleeps_remaining_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = object.__new__(UpwindDetectionsConnector)
    connector._stop_event = DummyStopEvent()
    connector._configuration = UpwindConnectorConfig(frequency=30, intake_key="test-key")

    logs: list[str] = []
    connector.log = lambda *, message, level: logs.append(f"{level}:{message}")
    connector.log_exception = lambda error: None

    def fake_next_batch() -> int:
        connector._stop_event.set()
        return 3

    connector.next_batch = fake_next_batch

    sleep_calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    clock = iter([100.0, 112.5])
    monkeypatch.setattr(connector_module.time, "time", lambda: next(clock))
    monkeypatch.setattr(connector_module.time, "sleep", fake_sleep)

    UpwindDetectionsConnector.run(connector)

    assert sleep_calls == [17.5]
    assert any("Pushed 3 detections" in entry for entry in logs)


def test_run_on_error_sleeps_full_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = object.__new__(UpwindDetectionsConnector)
    connector._stop_event = DummyStopEvent()
    connector._configuration = UpwindConnectorConfig(frequency=45, intake_key="test-key")

    captured_errors: list[str] = []
    connector.log = lambda *, message, level: None

    def fake_log_exception(error: Exception) -> None:
        captured_errors.append(str(error))
        connector._stop_event.set()

    connector.log_exception = fake_log_exception

    def fake_next_batch() -> int:
        raise RuntimeError("boom")

    connector.next_batch = fake_next_batch

    sleep_calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(connector_module.time, "sleep", fake_sleep)

    UpwindDetectionsConnector.run(connector)

    assert captured_errors == ["boom"]
    assert sleep_calls == [45]
