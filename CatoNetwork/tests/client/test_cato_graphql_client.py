"""Tests for Cato graphql client."""

import logging
from enum import Enum
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from aiolimiter import AsyncLimiter
from faker import Faker
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError, TransportServerError

from client.graphql_client import DEFAULT_TIMEOUT, CatoGraphQLClient, CatoRequestType


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
    client = CatoGraphQLClient(api_key=session_faker.uuid4(), account_id=session_faker.uuid4())
    client.set_rate_limiter(request_type, rate_limiter)

    # Check if the rate limiter is correctly set
    assert client._rate_limiters[request_type] == rate_limiter


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
    client = CatoGraphQLClient(api_key=session_faker.uuid4(), account_id=session_faker.uuid4())
    client.set_rate_limiter(request_type, rate_limiter)

    # Get the rate limiter
    retrieved_rate_limiter = client.get_rate_limiter(request_type)

    # Check if the retrieved rate limiter is the same as the one set
    assert retrieved_rate_limiter == rate_limiter


@pytest.mark.asyncio
async def test_get_rate_limiter_with_error(session_faker: Faker):
    """
    Test CatoGraphQLClient get_rate_limiter that should raise error.

    Args:
        session_faker: Faker
    """
    client = CatoGraphQLClient(api_key=session_faker.uuid4(), account_id=session_faker.uuid4())
    with pytest.raises(ValueError):
        client.get_rate_limiter(CatoRequestTypeFake.FAKE)


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


def events_feed_result(session_faker: Faker, marker: str) -> dict:
    return {
        "eventsFeed": {
            "marker": marker,
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


def mocked_client(session_faker: Faker) -> tuple[CatoGraphQLClient, MagicMock, MagicMock]:
    """Client whose gql Client is a mock returning a mocked session on `connect_async`."""
    client = CatoGraphQLClient(
        api_key=session_faker.uuid4(),
        account_id=session_faker.uuid4(),
        base_url=session_faker.url(),
        events_feed_rate_limiter=AsyncLimiter(100),
    )

    gql_client = MagicMock()
    session = MagicMock()
    session.client = gql_client
    gql_client.connect_async = AsyncMock(return_value=session)
    gql_client.close_async = AsyncMock()
    client._cato_clients = {CatoRequestType.EVENTS_FEED: gql_client}

    return client, gql_client, session


def test_transport_verifies_ssl_and_has_timeouts(session_faker: Faker):
    client = CatoGraphQLClient(api_key=session_faker.uuid4(), account_id=session_faker.uuid4())

    gql_client = client.cato_client(CatoRequestType.EVENTS_FEED)

    assert isinstance(gql_client.transport, AIOHTTPTransport)
    assert gql_client.transport.ssl is True
    assert gql_client.transport.timeout == DEFAULT_TIMEOUT == 60
    assert gql_client.execute_timeout == DEFAULT_TIMEOUT


def test_gql_transport_logger_is_not_verbose():
    assert logging.getLogger("gql.transport.aiohttp").getEffectiveLevel() >= logging.WARNING


@pytest.mark.asyncio
async def test_session_is_reused(session_faker: Faker):
    client, gql_client, session = mocked_client(session_faker)

    async with client._session(CatoRequestType.EVENTS_FEED) as first:
        assert first is session

    async with client._session(CatoRequestType.EVENTS_FEED) as second:
        assert second is session

    gql_client.connect_async.assert_awaited_once()
    gql_client.close_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_is_closed_on_transport_error(session_faker: Faker):
    client, gql_client, _ = mocked_client(session_faker)

    with pytest.raises(TransportServerError):
        async with client._session(CatoRequestType.EVENTS_FEED):
            raise TransportServerError("bad gateway", 502)

    gql_client.close_async.assert_awaited_once()
    assert client._sessions == {}

    async with client._session(CatoRequestType.EVENTS_FEED):
        pass

    assert gql_client.connect_async.await_count == 2


@pytest.mark.asyncio
async def test_session_is_kept_on_query_error(session_faker: Faker):
    client, gql_client, session = mocked_client(session_faker)

    with pytest.raises(TransportQueryError):
        async with client._session(CatoRequestType.EVENTS_FEED):
            raise TransportQueryError("invalid marker")

    gql_client.close_async.assert_not_awaited()
    assert client._sessions == {CatoRequestType.EVENTS_FEED: session}


@pytest.mark.asyncio
async def test_close_closes_open_sessions(session_faker: Faker):
    client, gql_client, _ = mocked_client(session_faker)

    await client.close()  # nothing open yet
    gql_client.close_async.assert_not_awaited()

    async with client._session(CatoRequestType.EVENTS_FEED):
        pass
    await client.close()

    gql_client.close_async.assert_awaited_once()
    assert client._sessions == {}


@pytest.mark.asyncio
async def test_load_events_feed(session_faker: Faker):
    """
    Test CatoGraphQLClient load_events_feed method.

    Args:
        session_faker: Faker
    """
    last_event_id = session_faker.uuid4()
    client, _, session = mocked_client(session_faker)
    session.execute = AsyncMock(return_value=events_feed_result(session_faker, last_event_id))

    response = await client.load_events_feed(last_event_id=last_event_id)

    assert response.marker == last_event_id
    assert response.fetchedCount == 10
    assert len(response.accounts) == 1
    assert len(response.accounts[0].records) == 10
    assert session.execute.call_args.kwargs["variable_values"] == {
        "accountIds": [client.account_id],
        "lastEventId": last_event_id,
    }


@pytest.mark.asyncio
async def test_load_events_feed_over_real_transport(session_faker: Faker):
    """End to end through gql and aiohttp against a local HTTP server."""
    requests: list[dict] = []
    result = events_feed_result(session_faker, "m1")

    async def handler(request: web.Request) -> web.Response:
        requests.append({"api_key": request.headers.get("x-api-key"), "body": await request.json()})
        return web.json_response({"data": result})

    app = web.Application()
    app.router.add_post("/graphql2", handler)

    async with TestServer(app) as server:
        client = CatoGraphQLClient(api_key="key", account_id="account", base_url=str(server.make_url("/graphql2")))

        assert (await client.load_events_feed()).marker == "m1"
        assert (await client.load_events_feed("m1")).marker == "m1"

        transport = client.cato_client(CatoRequestType.EVENTS_FEED).transport
        assert transport.session is not None  # the aiohttp session is kept between calls

        await client.close()
        assert transport.session is None

    assert [r["api_key"] for r in requests] == ["key", "key"]
    assert [r["body"]["variables"]["lastEventId"] for r in requests] == [None, "m1"]


def graphql_server(responses: list[web.Response]) -> tuple[web.Application, list[web.Request]]:
    """aiohttp app answering the given responses in order and recording the requests."""
    received: list[web.Request] = []

    async def handler(request: web.Request) -> web.Response:
        received.append(request)
        return responses[len(received) - 1]

    app = web.Application()
    app.router.add_post("/graphql2", handler)
    return app, received


@pytest.mark.asyncio
async def test_401_with_json_errors_body_is_a_query_error():
    app, _ = graphql_server(
        [web.json_response({"errors": [{"message": "Permission denied"}], "data": None}, status=401)]
    )

    async with TestServer(app) as server:
        client = CatoGraphQLClient(api_key="bad", account_id="account", base_url=str(server.make_url("/graphql2")))

        with pytest.raises(TransportQueryError) as excinfo:
            await client.load_events_feed()

        await client.close()

    assert excinfo.value.errors == [{"message": "Permission denied"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 503])
async def test_text_error_body_is_a_server_error_with_code(status: int):
    app, _ = graphql_server([web.Response(status=status, text="nope")])

    async with TestServer(app) as server:
        client = CatoGraphQLClient(api_key="key", account_id="account", base_url=str(server.make_url("/graphql2")))

        with pytest.raises(TransportServerError) as excinfo:
            await client.load_events_feed()

        await client.close()

    assert excinfo.value.code == status


@pytest.mark.asyncio
async def test_session_is_reopened_after_a_server_error(session_faker: Faker):
    app, received = graphql_server(
        [
            web.Response(status=503, text="unavailable"),
            web.json_response({"data": events_feed_result(session_faker, "m")}),
        ]
    )

    async with TestServer(app) as server:
        client = CatoGraphQLClient(api_key="key", account_id="account", base_url=str(server.make_url("/graphql2")))
        transport = client.cato_client(CatoRequestType.EVENTS_FEED).transport
        connect = AsyncMock(wraps=transport.connect)
        transport.connect = connect

        with pytest.raises(TransportServerError):
            await client.load_events_feed()
        assert transport.session is None
        assert client._sessions == {}

        assert (await client.load_events_feed()).marker == "m"
        assert transport.session is not None
        assert connect.await_count == 2

        await client.close()

    assert len(received) == 2
