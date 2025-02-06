"""Tests related to token refresher."""

import time
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

    await token_refresher.close()


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

    await token_refresher.close()


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

    await token_refresher.close()


@pytest.mark.asyncio
async def test_checkpoint_token_refresher_token_expiration(
    token_refresher: CheckpointTokenRefresher,
    session_faker: Faker,
):
    """
    Test `close` method.

    Args:
        token_refresher: CheckpointTokenRefresher
    """
    token_1 = CheckpointToken(
        token=session_faker.word(),
        csrf=session_faker.word(),
        expires=session_faker.word(),
        expiresIn=1,  # expire in 1 second
    )

    token_2 = CheckpointToken(
        token=session_faker.word(),
        csrf=session_faker.word(),
        expires=session_faker.word(),
        expiresIn=2,  # expire in 2 seconds
    )

    token_3 = CheckpointToken(
        token=session_faker.word(),
        csrf=session_faker.word(),
        expires=session_faker.word(),
        expiresIn=3,  # expire in 2 seconds
    )

    def get_result(token: CheckpointToken) -> dict[str, Any]:
        return {
            "success": True,
            "data": {
                "token": token.token,
                "csrf": token.csrf,
                "expires": token.expires,
                "expiresIn": token.expiresIn,
            },
        }

    with aioresponses() as mocked_responses:
        # We will fetch token 3 times during test
        mocked_responses.post(token_refresher.auth_url, status=200, payload=get_result(token_1))
        mocked_responses.post(token_refresher.auth_url, status=200, payload=get_result(token_2))
        mocked_responses.post(token_refresher.auth_url, status=200, payload=get_result(token_3))

        # We will fetch token 12 times with delay of 0.5 seconds
        # First token should expire in 1 second, second in 2 seconds and third in 3 seconds
        time.time()
        for i in range(6):
            async with token_refresher.with_access_token() as result:
                # first token should not be cached because it will expire in 1 second
                if i == 0:
                    assert result.token == token_1

                # second token should be cached because it will expire in 1 second
                # ttl is 2 seconds, but we cache only for 1 second
                # it should be returned from cache 2 times
                if i in [1, 2]:
                    assert result.token == token_2

                # third token should be cached because it will expire in 3 seconds
                # we cache it for 2 seconds. so it should be returned from cache 4 times
                if i > 2:
                    assert result.token == token_3

            time.sleep(0.5)

    await token_refresher.close()
