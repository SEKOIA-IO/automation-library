"""Tests related to token refresher."""

from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from client.schemas.token import Scope
from client.token_refresher import TrellixTokenRefresher


@pytest.mark.asyncio
async def test_trellix_refresher_refresh_token(http_token, session_faker, token_refresher_session):
    """
    Test TrellixTokenRefresher.refresh_token.

    Args:
        http_token: HttpToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = http_token.dict()

    token_refresher = TrellixTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
        Scope.complete_set_of_scopes(),
    )

    await token_refresher.refresh_token()

    assert token_refresher._token is not None
    assert token_refresher._token.token.access_token == http_token.access_token

    await token_refresher.close()


@pytest.mark.asyncio
async def test_trellix_refresher_refresh_token_1(http_token, session_faker):
    """
    Test TrellixTokenRefresher.refresh_token.

    Args:
        http_token: HttpToken
        session_faker: Faker
    """
    with aioresponses() as mocked_responses:
        auth_url = session_faker.uri()

        token_refresher = TrellixTokenRefresher(
            session_faker.word(), session_faker.word(), session_faker.word(), auth_url, Scope.complete_set_of_scopes()
        )

        mocked_responses.post(token_refresher.auth_url, status=200, payload=http_token.dict())

        await token_refresher.refresh_token()

        assert token_refresher._token is not None
        assert token_refresher._token.token.access_token == http_token.access_token

        await token_refresher.close()


@pytest.mark.asyncio
async def test_trellix_refresher_with_access_token(http_token, session_faker, token_refresher_session):
    """
    Test TrellixTokenRefresher.with_access_token method.

    Args:
        http_token: HttpToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = http_token.dict()

    token_refresher = TrellixTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
        Scope.complete_set_of_scopes(),
    )

    try:
        async with token_refresher.with_access_token() as access_token:
            assert access_token.token.access_token == http_token.access_token
    except Exception as e:
        pytest.fail(f"Exception occurred: {e}")

    assert token_refresher._token is not None
    assert token_refresher._token.token.access_token == http_token.access_token

    await token_refresher.close()


@pytest.mark.asyncio
async def test_trellix_refresher_instance(http_token, session_faker):
    """
    Test TrellixTokenRefresher.instance method.

    Args:
        http_token: HttpToken
        session_faker: Faker
    """
    client_id = session_faker.word()
    client_secret = session_faker.word()
    api_key = session_faker.word()
    base_url = session_faker.uri()

    base_url_different = session_faker.uri() + session_faker.word()

    instance1 = await TrellixTokenRefresher.instance(
        client_id, client_secret, api_key, base_url, Scope.complete_set_of_scopes()
    )
    instance2 = await TrellixTokenRefresher.instance(
        client_id, client_secret, api_key, base_url, Scope.complete_set_of_scopes()
    )
    instance3 = await TrellixTokenRefresher.instance(
        client_id,
        client_secret,
        api_key,
        base_url_different,
        {
            Scope.MI_USER_INVESTIGATE,
        },
    )

    assert instance1 is instance2

    assert instance3 is not instance1

    await instance1.close()
    await instance2.close()
    await instance3.close()
