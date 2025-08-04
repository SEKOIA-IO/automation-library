"""Tests related to token refresher."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from aioresponses import aioresponses

from wiz.client.token_refresher import WizTokenRefresher


@pytest.fixture
def token_refresher_session():
    """
    Mock session for WizTokenRefresher.

    Yields:
        MagicMock:
    """
    with patch.object(WizTokenRefresher, "_session") as session_mock:
        yield session_mock


@pytest.mark.asyncio
async def test_wiz_refresher_refresh_token_1(http_token, session_faker, auth_url):
    """
    Test WizTokenRefresher.refresh_token.

    Args:
        http_token: WizToken
        session_faker: Faker
        auth_url: str
    """
    with aioresponses() as mocked_responses:
        token_refresher = WizTokenRefresher(
            session_faker.word(),
            session_faker.word(),
            auth_url,
        )

        mocked_responses.post(auth_url, status=200, payload=http_token.dict())

        await token_refresher.refresh_token()

        assert token_refresher._token is not None
        assert token_refresher._token.access_token == http_token.access_token

        await token_refresher.close()


@pytest.mark.asyncio
async def test_wiz_refresher_with_access_token(http_token, session_faker, token_refresher_session):
    """
    Test WizTokenRefresher.with_access_token method.

    Args:
        http_token: WizToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.return_value = http_token.dict()

    token_refresher = WizTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
    )

    try:
        async with token_refresher.with_access_token() as access_token:
            assert access_token.access_token == http_token.access_token
    except Exception as e:
        pytest.fail(f"Exception occurred: {e}")

    assert token_refresher._token is not None
    assert token_refresher._token.access_token == http_token.access_token

    await token_refresher.close()


@pytest.mark.parametrize(
    "tenant_url, expected_auth_url",
    [
        ("https://sdfh12.app.wiz.us/iam/v1.0", "https://auth.app.wiz.us/oauth/token"),
        ("https://other.app.wiz.io/glasdij4r", "https://auth.app.wiz.io/oauth/token"),
        ("https://dkldk.test.gov.wiz.io/nnnnn", "https://auth.gov.wiz.io/oauth/token"),
        ("random", "https://auth.gov.wiz.io/oauth/token"),
    ],
)
@pytest.mark.asyncio
async def test_wiz_create_url_from_tenant(
    http_token, session_faker, token_refresher_session, tenant_url, expected_auth_url
):
    """
    Test WizTokenRefresher.auth_url

    Args:
        http_token: WizToken
        session_faker: Faker
        token_refresher_session: MagicMock
        tenant_url: str
        expected_auth_url: str
    """
    auth_url = WizTokenRefresher.create_url_from_tenant(tenant_url)

    assert auth_url == expected_auth_url


@pytest.mark.asyncio
async def test_wiz_refresher_always_provide_fresh_token(http_token, session_faker, token_refresher_session):
    """
    Test WizTokenRefresher.with_access_token method.

    Args:
        http_token: WizToken
        session_faker: Faker
        token_refresher_session: MagicMock
    """
    token_refresher_session.post = MagicMock()
    token_refresher_session.post.return_value.__aenter__.return_value.status = 200
    token_refresher_session.post.return_value.__aenter__.return_value.json.side_effect = [
        {
            "token_type": "Bearer",
            "expires_in": 2,
            "access_token": "token_expired_quickly",
            "refresh_token": "refresh_token",
        },
        {"token_type": "Bearer", "expires_in": 600, "access_token": "fresh_token", "refresh_token": "refresh_token"},
    ]

    token_refresher = WizTokenRefresher(
        session_faker.word(),
        session_faker.word(),
        session_faker.uri(),
    )

    await token_refresher.refresh_token()

    async with token_refresher.with_access_token() as token:
        assert token.access_token == "token_expired_quickly"

    await asyncio.sleep(1)

    async with token_refresher.with_access_token() as token:
        assert token.access_token == "token_expired_quickly"

    await asyncio.sleep(1)

    async with token_refresher.with_access_token() as token:
        assert token.access_token == "fresh_token"

    await asyncio.sleep(1)

    async with token_refresher.with_access_token() as token:
        assert token.access_token == "fresh_token"

    await asyncio.sleep(1)

    async with token_refresher.with_access_token() as token:
        assert token.access_token == "fresh_token"

    await token_refresher.close()
