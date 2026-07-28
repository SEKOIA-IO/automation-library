from datetime import UTC, datetime

import pytest
from cachetools import LRUCache

import upwind
from upwind import UpwindConnector, UpwindConnectorConfig, UpwindPage


class OffsetStore:
    def __init__(self, offset: datetime) -> None:
        self.offset = offset


def build_base_connector(offset: datetime) -> UpwindConnector:
    connector = object.__new__(UpwindConnector)
    connector.last_event_date = OffsetStore(offset)
    connector.events_cache = LRUCache(maxsize=100)
    return connector


@pytest.mark.asyncio
async def test_base_fetch_page_raises_not_implemented() -> None:
    connector = build_base_connector(datetime(2026, 7, 1, tzinfo=UTC))

    with pytest.raises(NotImplementedError):
        await UpwindConnector.fetch_page(connector, since=datetime(2026, 7, 1, tzinfo=UTC))


@pytest.mark.asyncio
async def test_single_run_handles_pagination_dedup_and_checkpoint_update() -> None:
    since = datetime(2026, 7, 1, tzinfo=UTC)
    connector = build_base_connector(since)

    calls: list[str | None] = []
    pages = [
        UpwindPage(
            items=[
                {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
                {"id": "evt-1", "last_seen_time": "2026-07-02T08:30:00Z"},
                {"category": "missing-id"},
                {"id": "evt-2", "first_seen_time": "2026-07-03T10:00:00Z"},
            ],
            next_page_token="next-token",
        ),
        UpwindPage(items=[{"id": "evt-3", "last_seen_time": "2026-06-30T09:00:00Z"}]),
    ]

    async def fake_fetch_page(*, since: datetime, page_token: str | None = None) -> UpwindPage:
        assert since == datetime(2026, 7, 1, tzinfo=UTC)
        calls.append(page_token)
        return pages.pop(0)

    pushed_payloads: list[list[str]] = []

    async def fake_push_data_to_intakes(outgoing: list[str]) -> list[str]:
        pushed_payloads.append(outgoing)
        return outgoing

    connector.fetch_page = fake_fetch_page
    connector.push_data_to_intakes = fake_push_data_to_intakes

    sent = await UpwindConnector.single_run(connector)

    assert sent == 3
    assert calls == [None, "next-token"]
    assert len(pushed_payloads) == 2
    assert len(pushed_payloads[0]) == 2
    assert len(pushed_payloads[1]) == 1
    assert connector.last_event_date.offset == datetime(2026, 7, 3, 10, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_single_run_stops_on_empty_page_without_pushing() -> None:
    since = datetime(2026, 7, 1, tzinfo=UTC)
    connector = build_base_connector(since)

    async def fake_fetch_page(*, since: datetime, page_token: str | None = None) -> UpwindPage:
        return UpwindPage(items=[])

    async def fake_push_data_to_intakes(outgoing: list[str]) -> list[str]:
        raise AssertionError("push_data_to_intakes should not be called")

    connector.fetch_page = fake_fetch_page
    connector.push_data_to_intakes = fake_push_data_to_intakes

    sent = await UpwindConnector.single_run(connector)

    assert sent == 0
    assert connector.last_event_date.offset == since


class DummySession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class DummyStopEvent:
    def __init__(self) -> None:
        self._is_set = False

    def is_set(self) -> bool:
        return self._is_set

    def set(self) -> None:
        self._is_set = True


@pytest.mark.asyncio
async def test_async_run_sleeps_remaining_frequency_and_closes_session(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = object.__new__(UpwindConnector)
    connector._stop_event = DummyStopEvent()
    connector._configuration = UpwindConnectorConfig(frequency=30, intake_key="test-key")
    connector._session = DummySession()

    logs: list[str] = []
    connector.log = lambda *, message, level: logs.append(f"{level}:{message}")
    connector.log_exception = lambda error: None

    async def fake_single_run() -> int:
        connector._stop_event.set()
        return 3

    connector.single_run = fake_single_run

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    clock = iter([100.0, 112.5])
    monkeypatch.setattr(upwind.time, "time", lambda: next(clock))
    monkeypatch.setattr(upwind.asyncio, "sleep", fake_sleep)

    await UpwindConnector.async_run(connector)

    assert sleep_calls == [17.5]
    assert any("Pushed 3 records" in entry for entry in logs)
    assert connector._session.closed is True


@pytest.mark.asyncio
async def test_async_run_on_error_sleeps_full_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = object.__new__(UpwindConnector)
    connector._stop_event = DummyStopEvent()
    connector._configuration = UpwindConnectorConfig(frequency=45, intake_key="test-key")
    connector._session = None

    captured_errors: list[str] = []
    connector.log = lambda *, message, level: None

    def fake_log_exception(error: Exception) -> None:
        captured_errors.append(str(error))
        connector._stop_event.set()

    connector.log_exception = fake_log_exception

    async def fake_single_run() -> int:
        raise RuntimeError("boom")

    connector.single_run = fake_single_run

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(upwind.asyncio, "sleep", fake_sleep)

    await UpwindConnector.async_run(connector)

    assert captured_errors == ["boom"]
    assert sleep_calls == [45]