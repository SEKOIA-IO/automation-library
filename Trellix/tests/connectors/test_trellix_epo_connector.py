"""Tests for Trellix EPO connector."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from aioresponses import aioresponses
from faker import Faker

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

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
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
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_edr_result = [epo_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(current_date, limit=connector.configuration.records_per_request),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_edr_result).decode("utf-8")),
            },
        )

        result = await connector.get_trellix_epo_events()

        assert result == pushed_events_ids


def _epo_event(
    epo_event_response: TrellixResponse[EpoEventAttributes], event_id: str, timestamp: datetime
) -> dict[str, Any]:
    event = epo_event_response.copy(deep=True)
    event.id = event_id
    event.attributes.timestamp = timestamp

    return orjson.loads(orjson.dumps(event.dict()))


@pytest.mark.asyncio
async def test_trellix_connector_checkpoint_moves_forward_between_iterations(
    connector: TrellixEpoConnector,
    http_token: HttpToken,
    epo_event_response: TrellixResponse[EpoEventAttributes],
):
    """The most recent event timestamp is saved after a push and used by the next iteration."""
    start_date = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
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
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict(), repeat=True)

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
    start_date = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()

    connector.push_data_to_intakes = AsyncMock(side_effect=RuntimeError("intake unavailable"))

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client
        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())
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
    start_date = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    with connector.context as cache:
        cache["last_event_date"] = start_date.isoformat()

    boundary = start_date + timedelta(minutes=10, milliseconds=500)
    already_pushed = _epo_event(epo_event_response, "event-1", boundary)
    same_second_new = _epo_event(epo_event_response, "event-2", boundary + timedelta(milliseconds=100))
    limit = connector.configuration.records_per_request

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client
        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())
        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict(), repeat=True)

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
