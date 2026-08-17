from datetime import UTC, datetime

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


def build_connector(offset: datetime, *, boundary_ids: list[str] | None = None) -> UpwindDetectionsConnector:
    connector = object.__new__(UpwindDetectionsConnector)
    connector.last_detection_date = OffsetStore(offset)
    connector._context = FakeContext(
        {"boundary_detection_ids": sorted(boundary_ids)} if boundary_ids is not None else {}
    )
    connector.configuration = UpwindConnectorConfig(
        frequency=60,
        intake_key="test-key",
    )
    connector._oauth_provider = OAuthTokenProvider()
    return connector


def test_frequency_returns_configured_value() -> None:
    connector = build_connector(datetime(2026, 7, 1, tzinfo=UTC))

    assert connector.frequency == 60


def test_iterate_yields_new_detections_and_updates_checkpoint() -> None:
    since = datetime(2026, 7, 1, tzinfo=UTC)
    connector = build_connector(since)

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

    connector.fetch_detections = fake_fetch_detections

    batches = list(connector.iterate())

    # The detection without a parseable timestamp is skipped.
    assert len(calls) == 1
    assert len(batches) == 1
    outgoing, most_recent = batches[0]
    assert len(outgoing) == 3
    assert most_recent == datetime(2026, 7, 3, 10, 5, tzinfo=UTC)
    assert connector.last_detection_date.offset == datetime(2026, 7, 3, 10, 5, tzinfo=UTC)
    # Only the detection at the new watermark is retained for boundary dedup.
    assert connector._context.data["boundary_detection_ids"] == ["evt-3"]


def test_iterate_skips_detections_at_or_before_checkpoint() -> None:
    since = datetime(2026, 7, 2, 8, 30, tzinfo=UTC)
    connector = build_connector(since, boundary_ids=["evt-1"])

    def fake_fetch_detections(*, since: datetime) -> list[dict[str, str]]:
        return [
            {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
            {"id": "evt-2", "last_seen_time": "2026-07-01T00:00:00Z"},
        ]

    connector.fetch_detections = fake_fetch_detections

    batches = list(connector.iterate())

    assert batches == []
    assert connector.last_detection_date.offset == since


def test_iterate_forwards_new_detection_at_checkpoint_boundary() -> None:
    since = datetime(2026, 7, 2, 8, 30, tzinfo=UTC)
    connector = build_connector(since, boundary_ids=["evt-1"])

    def fake_fetch_detections(*, since: datetime) -> list[dict[str, str]]:
        return [
            {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
            {"id": "evt-2", "last_seen_time": "2026-07-02T08:30:00Z"},
        ]

    connector.fetch_detections = fake_fetch_detections

    batches = list(connector.iterate())

    # evt-1 is deduped by boundary id, evt-2 is new at the same timestamp.
    assert len(batches) == 1
    outgoing, most_recent = batches[0]
    assert len(outgoing) == 1
    assert most_recent == since
    assert connector.last_detection_date.offset == since
    assert connector._context.data["boundary_detection_ids"] == ["evt-1", "evt-2"]

