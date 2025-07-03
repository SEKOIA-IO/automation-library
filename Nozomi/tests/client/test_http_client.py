import datetime
from typing import AsyncGenerator
from urllib.parse import urlencode

import pytest
from aioresponses import aioresponses
from faker.proxy import Faker

from nozomi_networks.client.errors import NozomiAuthError, NozomiError
from nozomi_networks.client.event_type import EventType
from nozomi_networks.client.http_client import NozomiClient

from ..helpers import aioresponses_callback


@pytest.fixture
async def http_client(nozomi_config: dict[str, str]) -> AsyncGenerator["NozomiClient", None]:
    """
    Create an instance of the client with the provided credentials.

    Args:
        nozomi_config: dict[str, str]

    Returns:
        NozomiClient:
    """
    client = NozomiClient(**nozomi_config)

    yield client

    await client.close()


@pytest.mark.asyncio
async def test_fetch_auth_token(
    http_client: NozomiClient, nozomi_config: dict[str, str], session_faker: Faker
) -> None:
    """
    Test fetching the authentication token from the Nozomi API.

    Args:
        http_client: NozomiClient
        nozomi_config: dict[str, str]
        session_faker: Faker
    """
    expected_token = session_faker.word()

    with aioresponses() as mocked_responses:
        auth_token_url = "{}/api/v1/keys/sign_in".format(nozomi_config.get("base_url"))
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback(
                {},
                response_headers={"Authorization": f"Bearer {expected_token}"},
                payload={
                    "key_name": nozomi_config["key_name"],
                    "key_token": nozomi_config["key_token"],
                },
                status=200,
            ),
        )

        await http_client.refresh_authorization()
        assert http_client._authorization == f"Bearer {expected_token}"


@pytest.mark.asyncio
async def test_fetch_auth_token_error(http_client: NozomiClient, nozomi_config: dict[str, str]) -> None:
    """
    Test error handling when fetching the authentication token from the Nozomi API.

    Args:
        http_client: NozomiClient
        nozomi_config: dict[str, str]
    """
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/api/v1/keys/sign_in".format(nozomi_config["base_url"])
        mocked_responses.post(
            auth_token_url,
            status=500,
        )

        with pytest.raises(NozomiError):
            await http_client.refresh_authorization()


@pytest.mark.asyncio
async def test_fetch_auth_token_no_access_token(http_client: NozomiClient, nozomi_config: dict[str, str]) -> None:
    """
    Test error handling when the response does not contain an access token.

    Args:
        http_client: NozomiClient
    """
    with aioresponses() as mocked_responses:
        auth_token_url = "{}/api/v1/keys/sign_in".format(nozomi_config["base_url"])
        mocked_responses.post(
            auth_token_url,
            status=200,
            payload={},
        )

        with pytest.raises(NozomiAuthError):
            await http_client.refresh_authorization()


@pytest.mark.asyncio
async def test_fetch_data_1(http_client: NozomiClient, nozomi_config: dict[str, str], session_faker: Faker) -> None:
    """
    Test fetching data from the Nozomi API.

    Args:
        http_client: NozomiClient
        nozomi_config: dict[str, str]
        session_faker: Faker
    """
    event_type = EventType.Alerts
    expected_data = {
        "data": [
            {
                "id": session_faker.uuid4(),
                "name": session_faker.word(),
                "value": session_faker.random_int(min=1, max=100),
            }
            for _ in range(300)
        ],
    }

    with aioresponses() as mocked_responses:
        base_url = nozomi_config["base_url"]
        auth_token_url = "{}/api/v1/keys/sign_in".format(base_url)
        auth_token = session_faker.word()
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback({}, response_headers={"Authorization": f"Bearer {auth_token}"}, status=200),
        )

        start_date = datetime.datetime.now()

        encoded_params_1 = urlencode(
            {
                "page": 1,
                "size": 100,
                "filter[record_created_at][gt]": int(start_date.timestamp() * 1000),
                "sort[record_created_at]": "asc",
            }
        )

        data_url = f"{base_url}/api/v1/{event_type.value}?{encoded_params_1}"

        mocked_responses.get(
            data_url,
            callback=aioresponses_callback(
                expected_data,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        encoded_params_2 = urlencode(
            {
                "page": 2,
                "size": 100,
                "filter[record_created_at][gt]": int(start_date.timestamp() * 1000),
                "sort[record_created_at]": "asc",
            }
        )

        data_url_2 = f"{base_url}/api/v1/{event_type.value}?{encoded_params_2}"
        mocked_responses.get(
            data_url_2,
            callback=aioresponses_callback(
                {"data": []},
                headers={
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        result = []
        async for item in http_client.fetch_events(event_type, start_date=start_date):
            result.append(item)

        assert result == expected_data["data"]


#
@pytest.mark.asyncio
async def test_fetch_data_2(http_client: NozomiClient, nozomi_config: dict[str, str], session_faker: Faker) -> None:
    """
    Test fetching data from the Nozomi API.

    Args:
        http_client: NozomiClient
    """
    event_type = EventType.Vulnerabilities
    expected_data_1 = {
        "data": [
            {
                "id": session_faker.uuid4(),
                "name": session_faker.word(),
                "value": session_faker.random_int(min=1, max=100),
            }
            for _ in range(300)
        ],
        "meta": {"count": 400},
    }

    expected_data_2 = {
        "data": [
            {
                "id": session_faker.uuid4(),
                "name": session_faker.word(),
                "value": session_faker.random_int(min=1, max=100),
            }
            for _ in range(100)
        ],
        "meta": {"count": 400},
    }

    with aioresponses() as mocked_responses:
        base_url = nozomi_config["base_url"]
        auth_token_url = "{}/api/v1/keys/sign_in".format(base_url)
        auth_token = session_faker.word()
        mocked_responses.post(
            auth_token_url,
            callback=aioresponses_callback({}, response_headers={"Authorization": f"Bearer {auth_token}"}, status=200),
        )

        start_date = datetime.datetime.now()

        encoded_params_1 = urlencode(
            {
                "page": 1,
                "size": 100,
                "filter[time][gt]": int(start_date.timestamp() * 1000),
                "sort[time]": "asc",
            }
        )

        data_url = f"{base_url}/api/v1/{event_type.value}?{encoded_params_1}"

        mocked_responses.get(
            data_url,
            callback=aioresponses_callback(
                expected_data_1,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        encoded_params_2 = urlencode(
            {
                "page": 2,
                "size": 100,
                "filter[time][gt]": int(start_date.timestamp() * 1000),
                "sort[time]": "asc",
            }
        )

        data_url_2 = f"{base_url}/api/v1/{event_type.value}?{encoded_params_2}"
        mocked_responses.get(
            data_url_2,
            callback=aioresponses_callback(
                expected_data_2,
                headers={
                    "Authorization": f"Bearer {auth_token}",
                },
                status=200,
            ),
        )

        result = []
        async for item in http_client.fetch_events(event_type, start_date=start_date):
            result.append(item)

        assert result == expected_data_1["data"] + expected_data_2["data"]
