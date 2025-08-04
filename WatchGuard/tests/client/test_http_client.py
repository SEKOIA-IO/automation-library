from typing import AsyncGenerator

import aiohttp
import pytest
from aioresponses import aioresponses
from faker.proxy import Faker

from watchguard.client.errors import WatchGuardError
from watchguard.client.http_client import WatchGuardClient, WatchGuardClientConfig
from watchguard.client.security_event import SecurityEvent

from ..helpers import aioresponses_callback


@pytest.fixture
def client_config(session_faker: Faker) -> WatchGuardClientConfig:
    """
    Create a set of credentials for the WatchGuard module.

    Returns:
        WatchGuardClientConfig:
    """
    return WatchGuardClientConfig(
        **{
            "username": session_faker.word(),
            "password": session_faker.word(),
            "account_id": session_faker.word(),
            "application_key": session_faker.word(),
            "base_url": session_faker.url(),
        }
    )


@pytest.fixture
async def http_client(client_config: WatchGuardClientConfig) -> AsyncGenerator["WatchGuardClient", None]:
    """
    Create an instance of the WatchGuardClient with the provided credentials.

    Args:
        client_config: WatchGuardClientConfig

    Returns:
        WatchGuardClient:
    """
    client = WatchGuardClient(client_config)

    yield client

    await client.close()


@pytest.mark.asyncio
async def test_fetch_auth_token(
    http_client: WatchGuardClient, client_config: WatchGuardClientConfig, session_faker: Faker
) -> None:
    """
    Test fetching the authentication token from the WatchGuard API.

    Args:
        http_client: WatchGuardClient
    """
    expected_token = session_faker.word()

    with aioresponses() as mocked_responses:
        auth_token_url = "{}/oauth/token".format(client_config.base_url)
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                {
                    "access_token": expected_token,
                },
                auth=aiohttp.BasicAuth(client_config.username, client_config.password),
                status=200,
            ),
        )

        token = await http_client.fetch_auth_token()

        assert token == expected_token
        assert http_client._auth_token == None


@pytest.mark.asyncio
async def test_fetch_auth_token_error(http_client: WatchGuardClient, client_config: WatchGuardClientConfig) -> None:
    """
    Test error handling when fetching the authentication token from the WatchGuard API.

    Args:
        http_client: WatchGuardClient
    """
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/oauth/token".format(client_config.base_url)
        mocked_responses.post(
            auth_token_url,
            status=500,
        )

        with pytest.raises(WatchGuardError):
            await http_client.fetch_auth_token()


@pytest.mark.asyncio
async def test_fetch_auth_token_no_access_token(
    http_client: WatchGuardClient, client_config: WatchGuardClientConfig
) -> None:
    """
    Test error handling when the response does not contain an access token.

    Args:
        http_client: WatchGuardClient
    """
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/oauth/token".format(client_config.base_url)
        mocked_responses.post(
            auth_token_url,
            status=200,
            payload={},
        )

        with pytest.raises(ValueError):
            await http_client.fetch_auth_token()


@pytest.mark.asyncio
async def test_fetch_data_1(
    http_client: WatchGuardClient, client_config: WatchGuardClientConfig, session_faker: Faker
) -> None:
    """
    Test fetching data from the WatchGuard API.

    Args:
        http_client: WatchGuardClient
    """
    event = SecurityEvent.BLOCKED_CONNECTIONS
    expected_data = {
        "data": [
            {
                "id": session_faker.uuid4(),
                "name": session_faker.word(),
                "value": session_faker.random_int(min=1, max=100),
            }
            for _ in range(3000)
        ],
    }

    with aioresponses() as mocked_responses:
        auth_token_url = "{}/oauth/token".format(client_config.base_url)
        expected_token = {
            "access_token": session_faker.word(),
        }
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                expected_token, auth=aiohttp.BasicAuth(client_config.username, client_config.password), status=200
            ),
        )

        data_url = "{0}/rest/endpoint-security/management/api/v1/accounts/{1}/securityevents/{2}/export/{3}".format(
            client_config.base_url, client_config.account_id, event.value, 1
        )

        mocked_responses.get(
            data_url,
            callback=aioresponses_callback(
                expected_data,
                headers={
                    "WatchGuard-API-Key": client_config.application_key,
                    "Authorization": f"Bearer {expected_token['access_token']}",
                },
                status=200,
            ),
        )

        result = []
        async for item in http_client.fetch_data(event):
            result.append(item)

        assert result == expected_data["data"]


@pytest.mark.asyncio
async def test_fetch_data_2(
    http_client: WatchGuardClient, client_config: WatchGuardClientConfig, session_faker: Faker
) -> None:
    """
    Test fetching data from the WatchGuard API.

    Args:
        http_client: WatchGuardClient
    """
    event = SecurityEvent.BLOCKED_CONNECTIONS
    expected_data = {
        "data": [
            {
                "id": session_faker.uuid4(),
                "name": session_faker.word(),
                "value": session_faker.random_int(min=1, max=100),
            }
            for _ in range(3000)
        ],
    }

    invalid_token = session_faker.word()
    http_client._auth_token = invalid_token

    with aioresponses() as mocked_responses:
        data_url = "{0}/rest/endpoint-security/management/api/v1/accounts/{1}/securityevents/{2}/export/{3}".format(
            client_config.base_url, client_config.account_id, event.value, 1
        )
        # First request with invalid token, should return 401
        mocked_responses.get(
            data_url,
            callback=aioresponses_callback(
                headers={
                    "WatchGuard-API-Key": client_config.application_key,
                    "Authorization": f"Bearer {invalid_token}",
                },
                status=401,
            ),
        )

        auth_token_url = "{}/oauth/token".format(client_config.base_url)
        expected_token = {
            "access_token": session_faker.word(),
        }
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                expected_token, auth=aiohttp.BasicAuth(client_config.username, client_config.password), status=200
            ),
        )

        mocked_responses.get(
            data_url,
            callback=aioresponses_callback(
                expected_data,
                headers={
                    "WatchGuard-API-Key": client_config.application_key,
                    "Authorization": f"Bearer {expected_token['access_token']}",
                },
                status=200,
            ),
        )

        result = []
        async for item in http_client.fetch_data(event):
            result.append(item)

        assert result == expected_data["data"]
