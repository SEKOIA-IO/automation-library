import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError, AnozrwayRateLimitError
from anozrway_modules.client.http_client import AnozrwayClient


class DummyLimiter:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


def build_response(status, payload=None, text=""):
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    response.json = AsyncMock(return_value=payload or {})
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None
    return response


def test_get_access_token_missing_session():
    client = AnozrwayClient({})
    with pytest.raises(AnozrwayError):
        asyncio.run(client._get_access_token())


def test_get_access_token_missing_credentials():
    client = AnozrwayClient({"anozrway_token_url": "https://auth.anozrway.test/oauth2/token"})
    client._session = MagicMock()
    client._rate_limiter = DummyLimiter()

    with pytest.raises(AnozrwayAuthError):
        asyncio.run(client._get_access_token())


def test_get_access_token_unauthorized():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(401, text="unauthorized")
    client._rate_limiter = DummyLimiter()

    with pytest.raises(AnozrwayAuthError):
        asyncio.run(client._get_access_token())


def test_get_access_token_status_error():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(500, text="server error")
    client._rate_limiter = DummyLimiter()

    with pytest.raises(AnozrwayError):
        asyncio.run(client._get_access_token())


def test_get_access_token_missing_token():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"token_type": "bearer"})
    client._rate_limiter = DummyLimiter()

    with pytest.raises(AnozrwayError):
        asyncio.run(client._get_access_token())


def test_get_access_token_cached():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._rate_limiter = DummyLimiter()
    client._access_token = "cached-token"
    client._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    token = asyncio.run(client._get_access_token())

    assert token == "cached-token"
    client._session.post.assert_not_called()


def test_get_access_token_success():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"access_token": "token", "expires_in": 120})
    client._rate_limiter = DummyLimiter()

    token = asyncio.run(client._get_access_token())

    assert token == "token"
    assert client._token_expires_at is not None
    assert client._access_token == "token"


def test_get_access_token_expired_token_triggers_refresh():
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_token_url": "https://auth.anozrway.test/oauth2/token",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"access_token": "new-token", "expires_in": 120})
    client._rate_limiter = DummyLimiter()
    client._access_token = "expired-token"
    client._token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    token = asyncio.run(client._get_access_token())

    assert token == "new-token"


def test_to_iso():
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert AnozrwayClient._to_iso(dt) == "2024-01-01T12:00:00Z"


def test_aenter_aexit(monkeypatch):
    session = MagicMock()
    session.close = AsyncMock()
    monkeypatch.setattr("anozrway_modules.client.http_client.aiohttp.ClientSession", lambda trust_env=True: session)

    client = AnozrwayClient({"anozrway_client_id": "client-id", "anozrway_client_secret": "client-secret"})
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    asyncio.run(client.__aenter__())
    assert client._session is session

    asyncio.run(client.__aexit__(None, None, None))
    session.close.assert_called_once()


def test_aexit_without_session():
    client = AnozrwayClient({})
    client._session = None

    asyncio.run(client.__aexit__(None, None, None))


def test_log_uses_trigger():
    trigger = MagicMock()
    client = AnozrwayClient({}, trigger=trigger)

    client.log("hello", "warning")

    trigger.log.assert_called_once_with(message="hello", level="warning")


# -------------------------------------------------------
# Tests for search_domain_v1 (/v1/domain/searches endpoint)
# -------------------------------------------------------


def test_search_domain_v1_retries_on_unauthorized(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401, text="unauthorized"),
        build_response(200, {"results": [{"id": 1}]}),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.search_domain_v1(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == [{"id": 1}]
    assert client._session.post.call_count == 2


def test_search_domain_v1_unauthorized_exhausted(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401, text="unauthorized"),
        build_response(401, text="unauthorized"),
        build_response(401, text="unauthorized"),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayAuthError):
        asyncio.run(
            client.search_domain_v1(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_search_domain_v1_includes_restrict_header(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
            "anozrway_x_restrict_access_token": "token-xyz",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"results": []})
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    asyncio.run(
        client.search_domain_v1(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    headers = client._session.post.call_args.kwargs["headers"]
    assert headers["x-restrict-access"] == "token-xyz"


def test_search_domain_v1_error_status(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(500, text="server error")
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayError):
        asyncio.run(
            client.search_domain_v1(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_search_domain_v1_rate_limit(monkeypatch):
    monkeypatch.setattr("anozrway_modules.client.http_client.asyncio.sleep", AsyncMock())

    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(429, text="rate limit"),
        build_response(429, text="rate limit"),
        build_response(429, text="rate limit"),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayRateLimitError):
        asyncio.run(
            client.search_domain_v1(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_search_domain_v1_non_list_results(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"results": "nope"})
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.search_domain_v1(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == []


def test_search_domain_v1_missing_session():
    client = AnozrwayClient({})

    with pytest.raises(AnozrwayError):
        asyncio.run(
            client.search_domain_v1(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


# -------------------------------------------------------
# Tests for fetch_events (Balise Pipeline /events endpoint)
# -------------------------------------------------------


def test_fetch_events_success(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(
        200, {"events": [{"nom_fuite": "leak-1", "timestamp": "2025-01-01T00:00:00Z"}]}
    )
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == [{"nom_fuite": "leak-1", "timestamp": "2025-01-01T00:00:00Z"}]
    call_args = client._session.post.call_args
    assert "/events" in call_args.args[0] or "/events" in str(call_args)


def test_fetch_events_retries_on_unauthorized(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401, text="unauthorized"),
        build_response(200, {"events": [{"nom_fuite": "leak-1"}]}),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == [{"nom_fuite": "leak-1"}]
    assert client._session.post.call_count == 2


def test_fetch_events_unauthorized_exhausted(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401, text="unauthorized"),
        build_response(401, text="unauthorized"),
        build_response(401, text="unauthorized"),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayAuthError):
        asyncio.run(
            client.fetch_events(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_fetch_events_includes_restrict_header(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
            "anozrway_x_restrict_access_token": "token-xyz",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": []})
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    headers = client._session.post.call_args.kwargs["headers"]
    assert headers["x-restrict-access"] == "token-xyz"


def test_fetch_events_error_status(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(500, text="server error")
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayError):
        asyncio.run(
            client.fetch_events(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_fetch_events_rate_limit(monkeypatch):
    monkeypatch.setattr("anozrway_modules.client.http_client.asyncio.sleep", AsyncMock())

    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(429, text="rate limit"),
        build_response(429, text="rate limit"),
        build_response(429, text="rate limit"),
    ]
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    with pytest.raises(AnozrwayRateLimitError):
        asyncio.run(
            client.fetch_events(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_fetch_events_non_list_results(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": "nope"})
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == []


def test_fetch_events_missing_session():
    client = AnozrwayClient({})

    with pytest.raises(AnozrwayError):
        asyncio.run(
            client.fetch_events(
                context="ctx",
                domain="example.com",
                start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            )
        )


def test_fetch_events_empty_events(monkeypatch):
    client = AnozrwayClient(
        {
            "anozrway_client_id": "client-id",
            "anozrway_client_secret": "client-secret",
            "anozrway_base_url": "https://balise.anozrway.test",
        }
    )
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": []})
    client._rate_limiter = DummyLimiter()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))

    results = asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )

    assert results == []
