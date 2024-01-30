"""Tests for Cato graphql client."""

from enum import Enum
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiolimiter import AsyncLimiter
from faker import Faker

from client.graphql_client import CatoGraphQLClient, CatoRequestType


def extend_enum(inherited_enum):
    """
    Extend enum wrapper.

    Only for testing purposes.

    Args:
        inherited_enum:
    """

    def wrapper(added_enum):
        joined = {}
        for item in inherited_enum:
            joined[item.name] = item.value

        for item in added_enum:
            joined[item.name] = item.value

        return Enum(added_enum.__name__, joined)

    return wrapper


@extend_enum(CatoRequestType)
class CatoRequestTypeFake(Enum):
    """Fake CatoRequestType."""

    FAKE = "fake"


@pytest.fixture
def mock_cato_graphql_client(session_faker: Faker) -> CatoGraphQLClient:
    """
    Mock CatoGraphQLClient.

    Args:
        session_faker: Faker

    Returns:
        CatoGraphQLClient:
    """
    # You can use the faker data to create a mock CatoGraphQLClient
    fake_api_key = session_faker.uuid4()
    fake_account_id = session_faker.uuid4()
    fake_base_url = session_faker.url()

    return CatoGraphQLClient(
        api_key=fake_api_key,
        account_id=fake_account_id,
        base_url=fake_base_url,
    )


@pytest.mark.asyncio
async def test_cato_graphql_client_init_without_limiters(session_faker: Faker):
    """
    Test CatoGraphQLClient init without limiters.

    Args:
        session_faker: Faker
    """
    # Generate fake data
    api_key = session_faker.uuid4()
    account_id = session_faker.uuid4()
    base_url = session_faker.url()

    # Create the CatoGraphQLClient instance
    client = CatoGraphQLClient(
        api_key=api_key,
        account_id=account_id,
        base_url=base_url,
    )

    # Check if the instance is created with correct attributes
    assert client.api_key == api_key
    assert client.account_id == account_id
    assert client.base_url == base_url

    assert CatoRequestType.ACCOUNT_METRICS in client._rate_limiters
    assert CatoRequestType.ACCOUNT_SNAPSHOT in client._rate_limiters
    assert CatoRequestType.AUDIT_FEED in client._rate_limiters
    assert CatoRequestType.ENTITY_LOOKUP in client._rate_limiters
    assert CatoRequestType.EVENTS_FEED in client._rate_limiters

    assert client._rate_limiters[CatoRequestType.ACCOUNT_METRICS].max_rate == 120
    assert client._rate_limiters[CatoRequestType.ACCOUNT_SNAPSHOT].max_rate == 120
    assert client._rate_limiters[CatoRequestType.AUDIT_FEED].max_rate == 5
    assert client._rate_limiters[CatoRequestType.ENTITY_LOOKUP].max_rate == 30
    assert client._rate_limiters[CatoRequestType.EVENTS_FEED].max_rate == 75


@pytest.mark.asyncio
async def test_cato_graphql_client_init_with_limiters(session_faker: Faker):
    """
    Test CatoGraphQLClient init with limiters.

    Args:
        session_faker: Faker
    """
    # Generate fake data
    api_key = session_faker.uuid4()
    account_id = session_faker.uuid4()
    base_url = session_faker.url()
    account_metrics_rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))
    account_snapshot_rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))
    audit_feed_rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))
    entity_lookup_rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))
    events_feed_rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))

    # Create the CatoGraphQLClient instance
    client = CatoGraphQLClient(
        api_key=api_key,
        account_id=account_id,
        base_url=base_url,
        account_metrics_rate_limiter=account_metrics_rate_limiter,
        account_snapshot_rate_limiter=account_snapshot_rate_limiter,
        audit_feed_rate_limiter=audit_feed_rate_limiter,
        entity_lookup_rate_limiter=entity_lookup_rate_limiter,
        events_feed_rate_limiter=events_feed_rate_limiter,
    )

    # Check if the instance is created with correct attributes
    assert client.api_key == api_key
    assert client.account_id == account_id
    assert client.base_url == base_url

    assert CatoRequestType.ACCOUNT_METRICS in client._rate_limiters
    assert CatoRequestType.ACCOUNT_SNAPSHOT in client._rate_limiters
    assert CatoRequestType.AUDIT_FEED in client._rate_limiters
    assert CatoRequestType.ENTITY_LOOKUP in client._rate_limiters
    assert CatoRequestType.EVENTS_FEED in client._rate_limiters

    assert client._rate_limiters[CatoRequestType.ACCOUNT_METRICS] == account_metrics_rate_limiter
    assert client._rate_limiters[CatoRequestType.ACCOUNT_SNAPSHOT] == account_snapshot_rate_limiter
    assert client._rate_limiters[CatoRequestType.AUDIT_FEED] == audit_feed_rate_limiter
    assert client._rate_limiters[CatoRequestType.ENTITY_LOOKUP] == entity_lookup_rate_limiter
    assert client._rate_limiters[CatoRequestType.EVENTS_FEED] == events_feed_rate_limiter


@pytest.mark.asyncio
async def test_set_rate_limiter(session_faker: Faker):
    """
    Test CatoGraphQLClient set_rate_limiter.

    Args:
        session_faker: Faker
    """
    # Generate fake data
    request_type = CatoRequestType.ACCOUNT_METRICS
    rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))

    # Set the rate limiter
    CatoGraphQLClient.set_rate_limiter(request_type, rate_limiter)

    # Check if the rate limiter is correctly set
    assert CatoGraphQLClient._rate_limiters[request_type] == rate_limiter


@pytest.mark.asyncio
async def test_get_rate_limiter(session_faker: Faker):
    """
    Test CatoGraphQLClient get_rate_limiter/set_rate_limiter.

    Args:
        session_faker: Faker
    """
    # Generate fake data
    request_type = CatoRequestType.ACCOUNT_METRICS
    rate_limiter = AsyncLimiter(session_faker.random_int(min=1, max=100))

    # Set the rate limiter
    CatoGraphQLClient.set_rate_limiter(request_type, rate_limiter)

    # Get the rate limiter
    retrieved_rate_limiter = CatoGraphQLClient.get_rate_limiter(request_type)

    # Check if the retrieved rate limiter is the same as the one set
    assert retrieved_rate_limiter == rate_limiter


@pytest.mark.asyncio
async def test_get_rate_limiter_with_error(session_faker: Faker):
    """
    Test CatoGraphQLClient get_rate_limiter that should raise error.

    Args:
        session_faker: Faker
    """
    with pytest.raises(ValueError):
        CatoGraphQLClient.get_rate_limiter(CatoRequestTypeFake.FAKE)


@pytest.mark.asyncio
async def test_generate_cato_client(session_faker: Faker):
    """
    Test CatoGraphQLClient cato_client method.

    Args:
        session_faker: Faker
    """
    client = CatoGraphQLClient(
        api_key=session_faker.uuid4(),
        account_id=session_faker.uuid4(),
        events_feed_rate_limiter=AsyncLimiter(session_faker.random_int(min=1, max=100)),
    )
    assert client._cato_clients is None

    result1 = client.cato_client(CatoRequestType.EVENTS_FEED)

    assert client._cato_clients is not None
    assert client._cato_clients == {CatoRequestType.EVENTS_FEED: result1}
    assert client.cato_client(CatoRequestType.EVENTS_FEED) == result1

    result2 = client.cato_client(CatoRequestType.AUDIT_FEED)

    assert client._cato_clients == {
        CatoRequestType.EVENTS_FEED: result1,
        CatoRequestType.AUDIT_FEED: result2,
    }
    assert client.cato_client(CatoRequestType.AUDIT_FEED) == result2
    assert client.cato_client(CatoRequestType.EVENTS_FEED) == result1


@pytest.mark.asyncio
async def test_session(session_faker: Faker):
    """
    Test CatoGraphQLClient _session method.

    Args:
        session_faker: Faker
    """
    client = CatoGraphQLClient(
        api_key=session_faker.uuid4(),
        account_id=session_faker.uuid4(),
        events_feed_rate_limiter=AsyncLimiter(session_faker.random_int(min=1, max=100)),
    )

    events_feed_mock = MagicMock()
    entity_lookup_mock = MagicMock()
    audit_feed_mock = MagicMock()
    account_metrics_mock = MagicMock()
    account_snapshot_mock = MagicMock()

    client._cato_clients = {
        CatoRequestType.EVENTS_FEED: events_feed_mock,
        CatoRequestType.ENTITY_LOOKUP: entity_lookup_mock,
        CatoRequestType.AUDIT_FEED: audit_feed_mock,
        CatoRequestType.ACCOUNT_METRICS: account_metrics_mock,
        CatoRequestType.ACCOUNT_SNAPSHOT: account_snapshot_mock,
    }

    async with client._session(CatoRequestType.EVENTS_FEED) as session:
        assert session == events_feed_mock

    async with client._session(CatoRequestType.ENTITY_LOOKUP) as session:
        assert session == entity_lookup_mock

    async with client._session(CatoRequestType.AUDIT_FEED) as session:
        assert session == audit_feed_mock

    async with client._session(CatoRequestType.ACCOUNT_METRICS) as session:
        assert session == account_metrics_mock

    async with client._session(CatoRequestType.ACCOUNT_SNAPSHOT) as session:
        assert session == account_snapshot_mock


@pytest.mark.asyncio
async def test_load_events_feed(session_faker: Faker):
    """
    Test CatoGraphQLClient load_events_feed method.

    Args:
        session_faker: Faker
    """
    # Generate fake data
    api_key = session_faker.uuid4()
    account_id = session_faker.uuid4()
    last_event_id = session_faker.uuid4()
    base_url = session_faker.url()

    # Create the CatoGraphQLClient instance
    client = CatoGraphQLClient(
        api_key=api_key,
        account_id=account_id,
        base_url=base_url,
        events_feed_rate_limiter=AsyncLimiter(session_faker.random_int(min=1, max=100)),
    )

    result_data = {
        "eventsFeed": {
            "marker": last_event_id,
            "fetchedCount": 10,
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

    client._cato_clients = {
        CatoRequestType.EVENTS_FEED: MagicMock(),
    }
    client._cato_clients[CatoRequestType.EVENTS_FEED].execute_async = AsyncMock(return_value=result_data)

    # Call the load_events_feed method
    response = await client.load_events_feed(last_event_id=last_event_id)

    # Check if the response is correctly parsed
    assert response.marker == last_event_id
    assert response.fetchedCount == 10
    assert len(response.accounts) == 1
    assert len(response.accounts[0].records) == 10
