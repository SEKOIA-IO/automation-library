from datetime import UTC, datetime

import pytest
from cachetools import LRUCache

from upwind import UpwindConnector, UpwindPage


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