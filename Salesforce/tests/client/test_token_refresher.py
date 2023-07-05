"""Tests related to token refresher."""

from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from client.token_refresher import SalesforceTokenRefresher


@pytest.mark.asyncio
async def test_salesforce_refresher_refresh_token(http_token, session_faker, token_refresher_session):
    """
    Test SalesforceTokenRefresher.refresh_token.

    Args:
        http_token: HttpToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = token_data

    token_refresher = SalesforceTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
        session_faker.pyint(),
    )

    await token_refresher.refresh_token()

    assert token_refresher._token is not None
    assert token_refresher._token.token.access_token == token_data["access_token"]

    await token_refresher.close()


@pytest.mark.asyncio
async def test_salesforce_refresher_refresh_token_1(http_token, session_faker):
    """
    Test SalesforceTokenRefresher.refresh_token.

    Args:
        http_token: HttpToken
        session_faker: Faker
    """
    with aioresponses() as mocked_responses:
        auth_url = session_faker.uri()

        token_data = http_token.dict()
        token_data["id"] = token_data["tid"]

        token_refresher = SalesforceTokenRefresher(
            session_faker.word(),
            session_faker.word(),
            auth_url,
            session_faker.pyint(),
        )

        mocked_responses.post(
            "{0}/services/oauth2/token?grant_type=client_credentials".format(auth_url), status=200, payload=token_data
        )

        await token_refresher.refresh_token()

        assert token_refresher._token is not None
        assert token_refresher._token.token.access_token == token_data["access_token"]

        await token_refresher.close()


@pytest.mark.asyncio
async def test_salesforce_refresher_with_access_token(http_token, session_faker, token_refresher_session):
    """
    Test SalesforceTokenRefresher.with_access_token method.

    Args:
        http_token: HttpToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = token_data

    token_refresher = SalesforceTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
        session_faker.pyint(),
    )

    try:
        async with token_refresher.with_access_token() as access_token:
            assert access_token.token.access_token == token_data["access_token"]
    except Exception as e:
        pytest.fail(f"Exception occurred: {e}")

    assert token_refresher._token is not None
    assert token_refresher._token.token.access_token == token_data["access_token"]

    await token_refresher.close()


@pytest.mark.asyncio
async def test_salesforce_refresher_instance(http_token, session_faker, token_refresher_session):
    """
    Test SalesforceTokenRefresher.instance method.

    Args:
        http_token: HttpToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_data = http_token.dict()
    token_data["id"] = token_data["tid"]

    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = token_data

    client_id = session_faker.word()
    client_secret = session_faker.word()
    auth_url = session_faker.uri()
    ttl = session_faker.pyint()

    auth_url_different = session_faker.uri() + session_faker.word()

    instance1 = await SalesforceTokenRefresher.instance(client_id, client_secret, auth_url, ttl)
    instance2 = await SalesforceTokenRefresher.instance(client_id, client_secret, auth_url, ttl)
    instance3 = await SalesforceTokenRefresher.instance(client_id, client_secret, auth_url_different, ttl)

    assert instance1.client_id == client_id
    assert instance1.client_secret == client_secret
    assert instance1.auth_url == auth_url
    assert instance1.token_ttl == ttl

    assert instance1 is instance2
    assert instance1.client_id == instance2.client_id
    assert instance1.client_secret == instance2.client_secret
    assert instance1.auth_url == instance2.auth_url
    assert instance1.token_ttl == instance2.token_ttl

    assert instance3 is not instance1
    assert instance3.client_id == instance1.client_id
    assert instance3.client_secret == instance1.client_secret
    assert instance3.auth_url == auth_url_different
    assert instance3.token_ttl == instance1.token_ttl

    await instance1.close()
    await instance2.close()
    await instance3.close()
