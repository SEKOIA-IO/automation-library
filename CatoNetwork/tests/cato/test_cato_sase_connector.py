"""Tests for Cato SASE connector."""

from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from sekoia_automation import constants

from cato.cato_sase_connector import CatoModule, CatoSaseConnector, CatoSaseConnectorConfig
from client.schemas.events_feed import EventsFeedResponseSchema


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
def api_key(session_faker) -> str:
    """
    Generate random api_key.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def account_id(session_faker) -> str:
    """
    Generate random account_id.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


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
def connector(
    symphony_storage: str, api_key: str, account_id: str, pushed_events_ids: list[str], session_faker: Faker
) -> CatoSaseConnector:
    """
    Generate connector.

    Args:
        symphony_storage: str
        api_key: str
        account_id: str
        pushed_events_ids: list[str]
        session_faker: Faker

    Returns:
        CatoSaseConnector:
    """
    module = CatoModule()
    connector_config = CatoSaseConnectorConfig(
        intake_key=session_faker.word(),
    )

    trigger = CatoSaseConnector(
        module=module,
        data_path=symphony_storage,
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    trigger.push_events_to_intakes = MagicMock()
    trigger.push_events_to_intakes.return_value = pushed_events_ids

    trigger.module.configuration = {
        "api_key": api_key,
        "account_id": account_id,
    }

    trigger.configuration = connector_config

    return trigger


@pytest.mark.asyncio
async def test_cato_sase_connector_latest_events_feed_id(connector: CatoSaseConnector, session_faker: Faker):
    """
    Test `latest_events_feed_id`.

    Args:
        connector: CatoSaseConnector
        session_faker: Faker
    """
    with connector.context as cache:
        cache["latest_events_feed_id"] = None

    assert connector.latest_events_feed_id is None

    random_feed_id = session_faker.uuid4()
    with connector.context as cache:
        cache["latest_events_feed_id"] = random_feed_id

    assert connector.latest_events_feed_id == random_feed_id


@pytest.mark.asyncio
async def test_cato_sase_connector_cato_client(connector: CatoSaseConnector, session_faker: Faker):
    """
    Test `latest_events_feed_id`.

    Args:
        connector: CatoSaseConnector
        session_faker: Faker
    """
    connector._cato_client = None

    client = connector.cato_client

    assert client is not None
    assert client.api_key == connector.module.configuration.api_key
    assert client.account_id == connector.module.configuration.account_id
    assert client.base_url == "https://api.catonetworks.com/api/v1/graphql2"

    assert connector.cato_client == client


@pytest.mark.asyncio
async def test_cato_sase_connector_get_cato_events_with_marker(
    connector: CatoSaseConnector, pushed_events_ids: list[str], session_faker: Faker
):
    """
    Test `latest_events_feed_id`.

    Args:
        connector: CatoSaseConnector
        session_faker: Faker
    """
    events_feed_response = {
        "eventsFeed": {
            "marker": session_faker.uuid4(),
            "fetchedCount": session_faker.random_int(min=1, max=100),
            "accounts": [
                {
                    "records": [
                        {
                            "time": session_faker.date_time().isoformat(),
                            "fieldsMap": {
                                "field1": session_faker.word(),
                                "field2": session_faker.random_int(min=1, max=100),
                            },
                        }
                        for _ in range(10)
                    ]
                }
            ],
        }
    }

    connector._cato_client = MagicMock()
    connector._cato_client.load_events_feed = AsyncMock(
        return_value=EventsFeedResponseSchema(**events_feed_response["eventsFeed"]),
    )

    assert connector.latest_events_feed_id is None
    assert await connector.get_cato_events() == pushed_events_ids
    assert connector.latest_events_feed_id == events_feed_response["eventsFeed"]["marker"]


@pytest.mark.asyncio
async def test_cato_sase_connector_get_cato_events_empty_response(
    connector: CatoSaseConnector, pushed_events_ids: list[str], session_faker: Faker
):
    """
    Test `latest_events_feed_id`.

    Args:
        connector: CatoSaseConnector
        session_faker: Faker
    """
    events_feed_response = {
        "eventsFeed": {
            "marker": "",
            "fetchedCount": 0,
            "accounts": [],
        }
    }

    connector._cato_client = MagicMock()
    connector._cato_client.load_events_feed = AsyncMock(
        return_value=EventsFeedResponseSchema(**events_feed_response["eventsFeed"]),
    )

    assert connector.latest_events_feed_id is None
    assert await connector.get_cato_events() == pushed_events_ids
    assert connector.latest_events_feed_id is None
