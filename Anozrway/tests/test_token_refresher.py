import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError
from anozrway_modules.client.token_refresher import AnozrwayTokenRefresher


def build_response(status, payload=None, text=""):
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    response.json = AsyncMock(return_value=payload or {})
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None
    return response


def make_refresher(**kwargs):
    defaults = dict(
        client_id="client-id",
        client_secret="client-secret",
        token_url="https://auth.anozrway.test/oauth2/token",
    )
    defaults.update(kwargs)
    r = AnozrwayTokenRefresher(**defaults)
    return r


def test_get_token_missing_credentials():
    refresher = AnozrwayTokenRefresher(
        client_id="",
        client_secret="",
        token_url="https://auth.anozrway.test/oauth2/token",
    )
    with pytest.raises(AnozrwayAuthError, match="Missing"):
        asyncio.run(refresher.get_token())


def test_get_token_unauthorized():
    refresher = make_refresher()
    session = MagicMock()
    session.post.return_value = build_response(401, text="unauthorized")
    refresher._session = session

    with pytest.raises(AnozrwayAuthError, match="unauthorized"):
        asyncio.run(refresher.get_token())


def test_get_token_status_error():
    refresher = make_refresher()
    session = MagicMock()
    session.post.return_value = build_response(500, text="server error")
    refresher._session = session

    with pytest.raises(AnozrwayError, match="Token request failed"):
        asyncio.run(refresher.get_token())


def test_get_token_missing_access_token():
    refresher = make_refresher()
    session = MagicMock()
    session.post.return_value = build_response(200, {"token_type": "bearer"})
    refresher._session = session

    with pytest.raises(AnozrwayError, match="missing access_token"):
        asyncio.run(refresher.get_token())


def test_get_token_success():
    refresher = make_refresher()
    session = MagicMock()
    session.post.return_value = build_response(200, {"access_token": "tok", "expires_in": 3600})
    refresher._session = session

    result = asyncio.run(refresher.get_token())

    assert result.token.access_token == "tok"
    assert result.ttl == 3300  # max(60, 3600-300)


def test_get_token_short_expiry_clamped():
    refresher = make_refresher()
    session = MagicMock()
    session.post.return_value = build_response(200, {"access_token": "tok", "expires_in": 200})
    refresher._session = session

    result = asyncio.run(refresher.get_token())
    assert result.ttl == 60  # max(60, 200-300) → max(60, -100) → 60
