"""Tests for Trellix connector."""
from datetime import datetime, timedelta, timezone
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock

import orjson
import pytest
from aioresponses import aioresponses
from sekoia_automation import constants

from client.schemas.token import Scope
from trellix.connector import TrellixEdrConnector, TrellixModule


@pytest.fixture
def symphony_storage() -> str:
    """
    Fixture for symphony temporary storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker
    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def connector(symphony_storage, pushed_events_ids, session_faker):
    """
    Fixture for TrellixEdrConnector.

    Args:
        symphony_storage:
        pushed_events_ids:
        session_faker:

    Returns:
        TrellixEdrConnector:
    """
    module = TrellixModule()
    trigger = TrellixEdrConnector(module=module, data_path=symphony_storage)

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    trigger.push_events_to_intakes = MagicMock()
    trigger.push_events_to_intakes.return_value = pushed_events_ids

    trigger.module.configuration = {
        "client_id": session_faker.word(),
        "client_secret": session_faker.word(),
        "api_key": session_faker.word(),
        "intake_key": session_faker.word(),
        "delay": session_faker.random.randint(1, 10),
        "ratelimit_per_minute": session_faker.random.randint(1, 10),
        "records_per_request": session_faker.random.randint(1, 100),
        "auth_url": session_faker.uri(),
        "base_url": session_faker.uri(),
    }

    return trigger


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
async def test_trellix_connector_push_events_wrapper(connector, pushed_events_ids, session_faker):
    """
    Test trellix connector push events.

    Args:
        connector: TrellixEdrConnector
        pushed_events_ids: list[str]
        session_faker: Faker
    """
    data = [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]

    assert await connector._push_events(data) == pushed_events_ids


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

        result = await connector.get_trellix_edr_events()

        assert result == pushed_events_ids
