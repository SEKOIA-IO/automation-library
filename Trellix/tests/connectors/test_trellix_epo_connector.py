"""Tests for Trellix EPO connector."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from aioresponses import CallbackResult, aioresponses
from faker import Faker
from yarl import URL

from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.token import HttpToken, Scope
from client.schemas.trellix_response import TrellixResponse
from connectors.trellix_epo_connector import TrellixEpoConnector, TrellixModule


@pytest.fixture
def connector(
    module: TrellixModule, symphony_storage: Path, pushed_events_ids: list[str], session_faker: Faker
) -> TrellixEpoConnector:
    """
    Fixture for TrellixEpoConnector.

    Args:
        module: TrellixModule,
        symphony_storage: Path,
        pushed_events_ids: list[str],
        session_faker: Faker

    Returns:
        TrellixEpoConnector:
    """
    trigger = TrellixEpoConnector(module=module, data_path=symphony_storage)

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    trigger.push_data_to_intakes = AsyncMock(return_value=pushed_events_ids)

    trigger.configuration = {
        "intake_key": session_faker.word(),
        "intake_server": session_faker.uri(),
        "ratelimit_per_minute": session_faker.random.randint(1000, 100000),
        "records_per_request": session_faker.random.randint(1, 100),
    }

    return trigger


@pytest.mark.asyncio
async def test_trellix_connector_last_event_date(connector: TrellixEpoConnector):
    """
    Test `last_event_date`.

    Args:
        connector: TrellixEpoConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(UTC).replace(microsecond=0)
    one_week_ago = current_date - timedelta(days=7)

    assert connector.last_event_date == one_week_ago

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.last_event_date == current_date

    with connector.context as cache:
        cache["last_event_date"] = (one_week_ago - timedelta(days=1)).isoformat()

    assert connector.last_event_date == one_week_ago


@pytest.mark.asyncio
async def test_trellix_connector_get_epo_events(
    connector: TrellixEpoConnector,
    session_faker: Faker,
    http_token: HttpToken,
    pushed_events_ids: list[str],
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """
    Test connector get epo events.

    Args:
        connector: TrellixEpoConnector
        session_faker: Faker
        http_token: HttpToken
        pushed_events_ids: list[str]
        epo_event_response: TrellixResponse[EpoEventAttributes]
    """
    current_date = datetime.now(UTC).replace(microsecond=0)

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())

        expected_edr_result = [epo_event_response.model_dump() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(current_date, limit=connector.configuration.records_per_request),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_edr_result).decode("utf-8")),
            },
        )
        # Requested only when the first page is full
        mocked_responses.get(
            http_client.epo_events_url(
                current_date,
                limit=connector.configuration.records_per_request,
                offset=connector.configuration.records_per_request,
            ),
            status=200,
            payload={"data": []},
        )

        result = await connector.get_trellix_epo_events()

        assert result == pushed_events_ids


def _epo_event(
    epo_event_response: TrellixResponse[EpoEventAttributes], event_id: str, timestamp: datetime
) -> dict[str, Any]:
    event = epo_event_response.copy(deep=True)
    event.id = event_id
    event.attributes.timestamp = timestamp

    return orjson.loads(orjson.dumps(event.model_dump()))


@pytest.mark.asyncio
async def test_trellix_connector_checkpoint_moves_forward_between_iterations(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """The most recent event timestamp is saved after a push and used by the next iteration."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()

    first_batch = [
        _epo_event(epo_event_response, "event-1", start_date + timedelta(minutes=1)),
        _epo_event(epo_event_response, "event-2", start_date + timedelta(minutes=10)),
    ]
    second_batch = [
        _epo_event(epo_event_response, "event-3", start_date + timedelta(minutes=20)),
    ]
    limit = connector.configuration.records_per_request

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client
        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump(), repeat=True)

        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=limit), status=200, payload={"data": first_batch}
        )
        await connector.get_trellix_epo_events()
        assert connector.last_event_date == start_date + timedelta(minutes=10)

        # Second iteration must query from the new checkpoint (an unmatched URL would raise)
        mocked_responses.get(
            http_client.epo_events_url(start_date + timedelta(minutes=10), limit=limit),
            status=200,
            payload={"data": second_batch},
        )
        await connector.get_trellix_epo_events()
        assert connector.last_event_date == start_date + timedelta(minutes=20)

    pushed = [call.args[0] for call in connector.push_data_to_intakes.call_args_list]
    assert [[orjson.loads(e)["timestamp"] for e in batch] for batch in pushed] == [
        [first_batch[0]["attributes"]["timestamp"], first_batch[1]["attributes"]["timestamp"]],
        [second_batch[0]["attributes"]["timestamp"]],
    ]


@pytest.mark.asyncio
async def test_trellix_connector_checkpoint_not_saved_when_push_fails(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """If the push to the intake fails, the checkpoint must not move."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()

    connector.push_data_to_intakes = AsyncMock(side_effect=RuntimeError("intake unavailable"))

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client
        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump())
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=connector.configuration.records_per_request),
            status=200,
            payload={"data": [_epo_event(epo_event_response, "event-1", start_date + timedelta(minutes=5))]},
        )

        with pytest.raises(RuntimeError):
            await connector.get_trellix_epo_events()

    assert connector.last_event_date == start_date


@pytest.mark.asyncio
async def test_trellix_connector_does_not_push_boundary_events_twice(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """
    The API filter is `GT` truncated to the second, so events of the checkpoint second are returned again.

    They must not be forwarded twice, while new events of that same second must still be forwarded.
    """
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()

    boundary = start_date + timedelta(minutes=10, milliseconds=500)
    already_pushed = _epo_event(epo_event_response, "event-1", boundary)
    same_second_new = _epo_event(epo_event_response, "event-2", boundary + timedelta(milliseconds=100))
    limit = connector.configuration.records_per_request

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client
        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump(), repeat=True)

        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=limit), status=200, payload={"data": [already_pushed]}
        )
        assert len(await connector.get_trellix_epo_events()) > 0

        mocked_responses.get(
            http_client.epo_events_url(boundary, limit=limit),
            status=200,
            payload={"data": [already_pushed, same_second_new]},
        )
        await connector.get_trellix_epo_events()

        mocked_responses.get(
            http_client.epo_events_url(boundary, limit=limit),
            status=200,
            payload={"data": [already_pushed, same_second_new]},
        )
        assert await connector.get_trellix_epo_events() == []

    pushed = [
        [orjson.loads(e)["timestamp"] for e in call.args[0]] for call in connector.push_data_to_intakes.call_args_list
    ]
    assert pushed == [[already_pushed["attributes"]["timestamp"]], [same_second_new["attributes"]["timestamp"]]]
    assert connector.last_event_date == boundary + timedelta(milliseconds=100)


PAGE_SIZE = 2


def _paginated_connector(connector: TrellixEpoConnector, start_date: datetime) -> TrellixEpoConnector:
    """Use a small fixed page size, a push mock that returns its input and a checkpoint at `start_date`."""
    connector.configuration = {
        **connector.configuration.model_dump(),
        "records_per_request": PAGE_SIZE,
    }
    connector.push_data_to_intakes = AsyncMock(side_effect=lambda events: events)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()
        cache["last_event_ids"] = []

    return connector


async def _mock_auth(mocked_responses: aioresponses, connector: TrellixEpoConnector, http_token: HttpToken) -> None:
    token_refresher = await connector.trellix_client._get_token_refresher(Scope.complete_set_of_scopes())
    mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.model_dump(), repeat=True)


def _pushed_ids(connector: TrellixEpoConnector) -> list[list[str]]:
    return [
        [orjson.loads(e)["autoguid"] for e in call.args[0]] for call in connector.push_data_to_intakes.call_args_list
    ]


def _event(epo_event_response: TrellixResponse[EpoEventAttributes], event_id: str, timestamp: datetime) -> dict:
    event = _epo_event(epo_event_response, event_id, timestamp)
    event["attributes"]["autoguid"] = event_id

    return event


@pytest.mark.asyncio
async def test_trellix_connector_drains_several_pages_in_one_run(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """Without `links`, pages are read with `page[offset]` until a page is not full; one push per page."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 6)]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        for offset in (0, 2, 4):
            mocked_responses.get(
                http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": events[offset : offset + PAGE_SIZE]},
            )

        result = await connector.get_trellix_epo_events()

    assert len(result) == 5
    assert _pushed_ids(connector) == [["event-1", "event-2"], ["event-3", "event-4"], ["event-5"]]

    # Checkpoint after the multi-page run: newest event of the last page
    assert connector.last_event_date == start_date + timedelta(minutes=5)
    with connector.context as cache:
        assert cache["last_event_ids"] == ["event-5"]


@pytest.mark.asyncio
async def test_trellix_connector_reads_exact_multiple_of_page_size(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """When the last page is full, the next (empty) page ends the run without any push."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 3)]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE), status=200, payload={"data": events}
        )
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=2), status=200, payload={"data": []}
        )

        assert len(await connector.get_trellix_epo_events()) == 2

    assert connector.push_data_to_intakes.await_count == 1
    assert connector.last_event_date == start_date + timedelta(minutes=2)


@pytest.mark.asyncio
async def test_trellix_connector_empty_page(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
):
    """An empty first page: nothing pushed, checkpoint unchanged."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        mocked_responses.get(
            connector.trellix_client.epo_events_url(start_date, limit=PAGE_SIZE),
            status=200,
            payload={"data": [], "links": {"self": "/epo/v2/events", "next": None}},
        )

        assert await connector.get_trellix_epo_events() == []

    connector.push_data_to_intakes.assert_not_awaited()
    assert connector.last_event_date == start_date


@pytest.mark.asyncio
async def test_trellix_connector_follows_links_next(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """When the API returns JSON:API `links`, `links.next` (absolute or relative) is followed and its absence ends."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 7)]
    http_client = connector.trellix_client
    base_url = http_client.base_url

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE),
            status=200,
            payload={"data": events[0:2], "links": {"next": f"{base_url}/epo/v2/events?page%5Bcursor%5D=abc"}},
        )
        mocked_responses.get(
            f"{base_url}/epo/v2/events?page%5Bcursor%5D=abc",
            status=200,
            payload={"data": events[2:4], "links": {"next": "/epo/v2/events?page%5Bcursor%5D=def"}},
        )
        mocked_responses.get(
            # A relative link is resolved against the host of base_url
            f"{URL(base_url).origin()}/epo/v2/events?page%5Bcursor%5D=def",
            status=200,
            # Full page, but no `next` link: this is the last page
            payload={"data": events[4:6], "links": {"self": "/epo/v2/events", "next": None}},
        )

        assert len(await connector.get_trellix_epo_events()) == 6

    assert _pushed_ids(connector) == [["event-1", "event-2"], ["event-3", "event-4"], ["event-5", "event-6"]]
    assert connector.last_event_date == start_date + timedelta(minutes=6)


@pytest.mark.asyncio
async def test_trellix_connector_ignores_next_link_to_another_host(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """A `links.next` to another host is never requested (it would receive the credentials)."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 3)]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        mocked_responses.get(
            connector.trellix_client.epo_events_url(start_date, limit=PAGE_SIZE),
            status=200,
            payload={"data": events, "links": {"next": "https://evil.example.com/epo/v2/events?page%5Boffset%5D=2"}},
        )

        assert len(await connector.get_trellix_epo_events()) == 2

    assert connector.push_data_to_intakes.await_count == 1


@pytest.mark.asyncio
async def test_trellix_connector_checkpoint_saved_before_next_page(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """The checkpoint of page 1 is persisted before page 2 is requested."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 4)]
    checkpoints_seen: list[datetime] = []

    def page_2_callback(url: Any, **kwargs: Any) -> CallbackResult:
        checkpoints_seen.append(connector.last_event_date)
        return CallbackResult(status=200, payload={"data": events[2:]})

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE), status=200, payload={"data": events[:2]}
        )
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=2), callback=page_2_callback
        )

        await connector.get_trellix_epo_events()

    assert checkpoints_seen == [start_date + timedelta(minutes=2)]
    assert connector.last_event_date == start_date + timedelta(minutes=3)


@pytest.mark.asyncio
async def test_trellix_connector_more_events_than_page_size_in_one_second(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """
    More than `records_per_request` events share one second: the run pages through that second instead of
    being stuck on it, and a later run that reads the second again does not forward its events twice.
    """
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    busy_second = start_date + timedelta(minutes=10)
    same_second = [
        _event(epo_event_response, f"event-{i}", busy_second + timedelta(milliseconds=100 * i)) for i in range(1, 6)
    ]
    later = _event(epo_event_response, "event-later", busy_second + timedelta(seconds=1))

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        for offset in (0, 2, 4):
            mocked_responses.get(
                http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": same_second[offset : offset + PAGE_SIZE]},
            )
        await connector.get_trellix_epo_events()

        assert connector.last_event_date == busy_second + timedelta(milliseconds=500)
        with connector.context as cache:
            assert cache["last_event_ids"] == [f"event-{i}" for i in range(1, 6)]

        # Next run: `GT <busy second>` returns the busy second again, then the newer event
        window = [*same_second, later]
        for offset in (0, 2, 4):
            mocked_responses.get(
                http_client.epo_events_url(busy_second, limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": window[offset : offset + PAGE_SIZE]},
            )
        mocked_responses.get(
            http_client.epo_events_url(busy_second, limit=PAGE_SIZE, offset=6), status=200, payload={"data": []}
        )
        await connector.get_trellix_epo_events()

    assert _pushed_ids(connector) == [
        ["event-1", "event-2"],
        ["event-3", "event-4"],
        ["event-5"],
        ["event-later"],
    ]
    assert connector.last_event_date == busy_second + timedelta(seconds=1)
    with connector.context as cache:
        assert cache["last_event_ids"] == ["event-later"]


@pytest.mark.asyncio
async def test_trellix_connector_page_bound_does_not_stop_inside_start_second(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
    monkeypatch: pytest.MonkeyPatch,
):
    """The per-run page bound only applies once the checkpoint has left the second the run started from."""
    monkeypatch.setattr("connectors.trellix_epo_connector.MAX_PAGES_PER_RUN", 1)
    busy_second = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, busy_second + timedelta(milliseconds=50))
    events = [
        _event(epo_event_response, f"event-{i}", busy_second + timedelta(milliseconds=100 * i)) for i in range(1, 5)
    ] + [
        _event(epo_event_response, "event-5", busy_second + timedelta(seconds=1)),
        _event(epo_event_response, "event-6", busy_second + timedelta(seconds=2)),
    ]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        for offset in (0, 2, 4):
            mocked_responses.get(
                http_client.epo_events_url(busy_second, limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": events[offset : offset + PAGE_SIZE]},
            )

        await connector.get_trellix_epo_events()

    # Pages 1 and 2 stay in the start second; page 3 moves the checkpoint forward, then the bound applies
    assert connector.push_data_to_intakes.await_count == 3
    assert connector.last_event_date == busy_second + timedelta(seconds=2)


@pytest.mark.asyncio
async def test_trellix_connector_page_bound_per_run(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
    monkeypatch: pytest.MonkeyPatch,
):
    """A run reads at most MAX_PAGES_PER_RUN pages; the next run continues from the checkpoint."""
    monkeypatch.setattr("connectors.trellix_epo_connector.MAX_PAGES_PER_RUN", 2)
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 7)]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        for offset in (0, 2):
            mocked_responses.get(
                http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": events[offset : offset + PAGE_SIZE]},
            )

        # Page 3 is not mocked: requesting it would raise
        assert len(await connector.get_trellix_epo_events()) == 4

        mocked_responses.get(
            http_client.epo_events_url(start_date + timedelta(minutes=4), limit=PAGE_SIZE),
            status=200,
            payload={"data": events[4:]},
        )
        mocked_responses.get(
            http_client.epo_events_url(start_date + timedelta(minutes=4), limit=PAGE_SIZE, offset=2),
            status=200,
            payload={"data": []},
        )
        assert len(await connector.get_trellix_epo_events()) == 2

    assert connector.log.call_count >= 1
    assert connector.last_event_date == start_date + timedelta(minutes=6)


@pytest.mark.asyncio
async def test_trellix_connector_push_failure_during_pagination(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """
    The push of page 2 fails: the checkpoint stays at the last event of page 1, and the next run resumes
    from there without forwarding page 1 again.
    """
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    second = start_date + timedelta(minutes=1)
    # event-2 and event-3 share a second across the page boundary
    events = [
        _event(epo_event_response, "event-1", second),
        _event(epo_event_response, "event-2", second + timedelta(milliseconds=500)),
        _event(epo_event_response, "event-3", second + timedelta(milliseconds=700)),
        _event(epo_event_response, "event-4", second + timedelta(minutes=1)),
    ]
    connector.push_data_to_intakes = AsyncMock(side_effect=[["id-1", "id-2"], RuntimeError("intake unavailable")])

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE), status=200, payload={"data": events[:2]}
        )
        mocked_responses.get(
            http_client.epo_events_url(start_date, limit=PAGE_SIZE, offset=2), status=200, payload={"data": events[2:]}
        )

        with pytest.raises(RuntimeError):
            await connector.get_trellix_epo_events()

        assert connector.last_event_date == second + timedelta(milliseconds=500)
        with connector.context as cache:
            assert cache["last_event_ids"] == ["event-1", "event-2"]

        # Next run: `GT <second>` returns events 1 to 4 again, only 3 and 4 are forwarded
        connector.push_data_to_intakes = AsyncMock(side_effect=lambda events: events)
        mocked_responses.get(
            http_client.epo_events_url(second, limit=PAGE_SIZE), status=200, payload={"data": events[:2]}
        )
        mocked_responses.get(
            http_client.epo_events_url(second, limit=PAGE_SIZE, offset=2), status=200, payload={"data": events[2:]}
        )
        mocked_responses.get(
            http_client.epo_events_url(second, limit=PAGE_SIZE, offset=4), status=200, payload={"data": []}
        )
        await connector.get_trellix_epo_events()

    assert _pushed_ids(connector) == [["event-3", "event-4"]]
    assert connector.last_event_date == second + timedelta(minutes=1)


@pytest.mark.asyncio
async def test_trellix_connector_stops_paginating_when_stopped(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """When the connector is stopped during a run, no further page is requested."""
    start_date = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, start_date)
    events = [_event(epo_event_response, f"event-{i}", start_date + timedelta(minutes=i)) for i in range(1, 5)]

    def push_then_stop(batch: list[str]) -> list[str]:
        connector._stop_event.set()
        return batch

    connector.push_data_to_intakes = AsyncMock(side_effect=push_then_stop)

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        # Page 2 is not mocked: requesting it would raise
        mocked_responses.get(
            connector.trellix_client.epo_events_url(start_date, limit=PAGE_SIZE),
            status=200,
            payload={"data": events[:2]},
        )

        assert len(await connector.get_trellix_epo_events()) == 2

    assert connector.last_event_date == start_date + timedelta(minutes=2)


@pytest.mark.asyncio
async def test_trellix_connector_last_event_ids_are_bounded(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
    monkeypatch: pytest.MonkeyPatch,
):
    """Only the most recent MAX_LAST_EVENT_IDS ids of the checkpoint second are kept in context.json."""
    monkeypatch.setattr("connectors.trellix_epo_connector.MAX_LAST_EVENT_IDS", 3)
    busy_second = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    connector = _paginated_connector(connector, busy_second - timedelta(seconds=1))
    events = [
        _event(epo_event_response, f"event-{i}", busy_second + timedelta(milliseconds=100 * i)) for i in range(1, 6)
    ]

    with aioresponses() as mocked_responses:
        await _mock_auth(mocked_responses, connector, http_token)
        http_client = connector.trellix_client
        for offset in (0, 2, 4):
            mocked_responses.get(
                http_client.epo_events_url(busy_second - timedelta(seconds=1), limit=PAGE_SIZE, offset=offset),
                status=200,
                payload={"data": events[offset : offset + PAGE_SIZE]},
            )

        await connector.get_trellix_epo_events()

    with connector.context as cache:
        assert cache["last_event_ids"] == ["event-3", "event-4", "event-5"]


def test_trellix_epo_connector_run_without_existing_event_loop(connector):
    """run() must start its own event loop (no current loop exists on Python 3.14)."""
    connector.async_run = AsyncMock()

    connector.run()

    connector.async_run.assert_awaited_once()


def test_trellix_epo_connector_rate_limiters(connector: TrellixEpoConnector):
    """The per-minute and per-day limiters use the configured values over 60 s and 86400 s windows."""
    connector.configuration = {
        **connector.configuration.model_dump(),
        "ratelimit_per_minute": 42,
        "ratelimit_per_day": 1234,
    }
    connector._trellix_client = None

    http_client = connector.trellix_client

    assert http_client._rate_limiter is not None
    assert http_client._rate_limiter.max_rate == 42
    assert http_client._rate_limiter.time_period == 60
    assert http_client._rate_limiter_per_day is not None
    assert http_client._rate_limiter_per_day.max_rate == 1234
    assert http_client._rate_limiter_per_day.time_period == 86400
