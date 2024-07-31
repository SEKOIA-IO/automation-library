"""Tests for Trellix EPO connector."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
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
