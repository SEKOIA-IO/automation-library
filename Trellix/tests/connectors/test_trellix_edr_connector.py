"""Tests for Trellix connector."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from aioresponses import aioresponses

from client.schemas.token import Scope
from connectors.trellix_edr_connector import TrellixEdrConnector
from connectors.trellix_epo_connector import TrellixModule


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker
    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 100))]


@pytest.fixture
def connector(module: TrellixModule, symphony_storage, pushed_events_ids, session_faker) -> TrellixEdrConnector:
    """
    Fixture for TrellixEdrConnector.

    Args:
        symphony_storage:
        pushed_events_ids:
        session_faker:

    Returns:
        TrellixEdrConnector:
    """
    connector = TrellixEdrConnector(module=module, data_path=symphony_storage)

    # Mock the log function of trigger that requires network access to the api for reporting
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    connector.push_data_to_intakes = AsyncMock(return_value=pushed_events_ids)

    connector.configuration = {
        "intake_key": session_faker.word(),
        "intake_server": session_faker.uri(),
    }

    return connector


@pytest.mark.asyncio
async def test_trellix_connector_last_event_date(connector):
    """
    Test `last_event_date`.

    Args:
        connector: TrellixEdrConnector
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
    connector, session_faker, http_token, pushed_events_ids, edr_epo_event_response
):
    """
    Test salesforce connector get salesforce events.

    Args:
        connector: SalesforceConnector
        session_faker: Faker
        http_token: HttpToken
        edr_epo_event_response: TrellixEdrResponse
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    with aioresponses() as mocked_responses:
        http_client = connector.trellix_client

        token_refresher = await http_client._get_token_refresher(Scope.complete_set_of_scopes())

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        expected_edr_result = [edr_epo_event_response.dict() for _ in range(0, session_faker.pyint(max_value=100))]

        mocked_responses.get(
            http_client.epo_events_url(current_date, limit=connector.module.configuration.records_per_request),
            status=200,
            payload={
                "data": orjson.loads(orjson.dumps(expected_edr_result).decode("utf-8")),
            },
        )

        result = await connector.get_trellix_epo_events()

        assert result == pushed_events_ids
