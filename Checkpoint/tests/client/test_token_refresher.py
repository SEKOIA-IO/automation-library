"""Tests related to token refresher."""

from typing import Any

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.token_refresher import CheckpointServiceType, CheckpointToken, CheckpointTokenRefresher


@pytest.fixture
def token_refresher(session_faker: Faker) -> CheckpointTokenRefresher:
    """
    Get CheckpointTokenRefresher instance.

    Args:
        session_faker: Faker

    Returns:
        CheckpointTokenRefresher:
    """
    return CheckpointTokenRefresher(
        client_id=session_faker.pystr(),
        secret_key=session_faker.pystr(),
        auth_url=session_faker.url(),
    )


@pytest.mark.asyncio
async def test_checkpoint_token_refresher_get_instance(session_faker: Faker):
    """
    Test `get_instance` method.

    Args:
        session_faker: Faker
    """
    client_id = session_faker.pystr()
    secret_key = session_faker.pystr()
    auth_url = session_faker.url()

    assert await CheckpointTokenRefresher.get_instance(
        client_id, secret_key, auth_url, CheckpointServiceType.HARMONY_MOBILE
    ) is await CheckpointTokenRefresher.get_instance(
        client_id, secret_key, auth_url, CheckpointServiceType.HARMONY_MOBILE
    )

    assert await CheckpointTokenRefresher.get_instance(
        client_id, secret_key, auth_url, CheckpointServiceType.HARMONY_MOBILE
    ) is not await CheckpointTokenRefresher.get_instance(
        client_id, secret_key, session_faker.url(), CheckpointServiceType.HARMONY_MOBILE
    )


@pytest.mark.asyncio
async def test_checkpoint_token_refresher_get_token_success(
    token_refresher: CheckpointTokenRefresher, http_token: tuple[CheckpointToken, dict[str, Any]]
):
    """
    Test `get_token` method.

    Args:
        token_refresher: CheckpointTokenRefresher
        http_token: tuple[CheckpointToken, dict[str, Any]]
    """
    token_data, response = http_token

    with aioresponses() as mocked_responses:
        mocked_responses.post(token_refresher.auth_url, status=200, payload=response)

        result = await token_refresher.get_token()

        assert result.token == token_data


@pytest.mark.asyncio
async def test_checkpoint_token_refresher_get_token_error_1(
    token_refresher: CheckpointTokenRefresher, http_token: tuple[CheckpointToken, dict[str, Any]]
):
    """
    Test `get_token` method.

    Args:
        token_refresher: CheckpointTokenRefresher
        http_token: tuple[CheckpointToken, dict[str, Any]]
    """
    token_data, _ = http_token
    response = {
        "success": False,
        "data": token_data.dict(),
    }

    with aioresponses() as mocked_responses:
        mocked_responses.post(token_refresher.auth_url, status=200, payload=response)

        with pytest.raises(ValueError):
            await token_refresher.get_token()


@pytest.mark.asyncio
async def test_checkpoint_token_refresher_get_token_error_2(
    token_refresher: CheckpointTokenRefresher,
    session_faker: Faker,
):
    """
    Test `get_token` method.

    Args:
        token_refresher: CheckpointTokenRefresher
        session_faker: Faker
    """
    response = {
        "success": True,
        "random": session_faker.word(),
    }

    with aioresponses() as mocked_responses:
        mocked_responses.post(token_refresher.auth_url, status=200, payload=response)

        with pytest.raises(ValueError):
            await token_refresher.get_token()
