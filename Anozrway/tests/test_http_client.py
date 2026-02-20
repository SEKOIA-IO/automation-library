import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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


def make_client(**kwargs):
    defaults = dict(
        base_url="https://balise.anozrway.test",
        token_url="https://auth.anozrway.test/oauth2/token",
        client_id="client-id",
        client_secret="client-secret",
    )
    defaults.update(kwargs)
    return AnozrwayClient(**defaults)


def patch_get_token(client, token="token"):
    client._get_access_token = AsyncMock(return_value=token)


# -------------------------------------------------------
# _get_access_token delegates to token refresher
# -------------------------------------------------------


def test_get_access_token_delegates_to_refresher():
    client = make_client()

    refreshed = MagicMock()
    refreshed.token.access_token = "delegated-token"

    @asynccontextmanager
    async def fake_with_access_token():
        yield refreshed

    client._token_refresher.with_access_token = fake_with_access_token

    token = asyncio.run(client._get_access_token())
    assert token == "delegated-token"


# -------------------------------------------------------
# _to_iso
# -------------------------------------------------------


def test_to_iso():
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert AnozrwayClient._to_iso(dt) == "2024-01-01T12:00:00Z"


# -------------------------------------------------------
# __aenter__ / __aexit__
# -------------------------------------------------------


def test_aenter_aexit(monkeypatch):
    session = MagicMock()
    session.close = AsyncMock()
    monkeypatch.setattr("anozrway_modules.client.http_client.aiohttp.ClientSession", lambda trust_env=True: session)

    client = make_client()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(return_value="token"))
    monkeypatch.setattr(client._token_refresher, "close", AsyncMock())

    asyncio.run(client.__aenter__())
    assert client._session is session

    asyncio.run(client.__aexit__(None, None, None))
    session.close.assert_called_once()
    client._token_refresher.close.assert_called_once()


def test_aexit_without_session():
    client = make_client()
    client._session = None

    async def run():
        client._token_refresher.close = AsyncMock()
        await client.__aexit__(None, None, None)

    asyncio.run(run())


def test_aenter_closes_session_on_token_failure(monkeypatch):
    session = MagicMock()
    session.close = AsyncMock()
    monkeypatch.setattr("anozrway_modules.client.http_client.aiohttp.ClientSession", lambda trust_env=True: session)

    client = make_client()
    monkeypatch.setattr(client, "_get_access_token", AsyncMock(side_effect=AnozrwayAuthError("bad credentials")))

    with pytest.raises(AnozrwayAuthError):
        asyncio.run(client.__aenter__())

    session.close.assert_called_once()
    assert client._session is None


# -------------------------------------------------------
# log
# -------------------------------------------------------


def test_log_uses_trigger():
    trigger = MagicMock()
    client = make_client(trigger=trigger)
    client.log("hello", "warning")
    trigger.log.assert_called_once_with(message="hello", level="warning")


# -------------------------------------------------------
# _post_with_retry – missing session
# -------------------------------------------------------


def test_post_with_retry_missing_session():
    client = make_client()

    with pytest.raises(AnozrwayError, match="session not initialized"):
        asyncio.run(
            client._post_with_retry(
                "/events",
                {},
                result_key="events",
                unauthorized_msg="unauthorized",
                generic_error_msg="error",
            )
        )


# -------------------------------------------------------
# timeout type
# -------------------------------------------------------


def test_timeout_is_aiohttp_client_timeout():
    import aiohttp

    client = make_client(timeout_seconds=45)
    assert isinstance(client.timeout, aiohttp.ClientTimeout)
    assert client.timeout.total == 45


# -------------------------------------------------------
# search_domain_v1
# -------------------------------------------------------


def test_search_domain_v1_retries_on_unauthorized(monkeypatch):
    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401, text="unauthorized"),
        build_response(200, {"results": [{"id": 1}]}),
    ]
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [build_response(401)] * 3
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client(x_restrict_access="token-xyz")
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"results": []})
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(500, text="server error")
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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

    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [build_response(429)] * 3
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"results": "nope"})
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()

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
# fetch_events
# -------------------------------------------------------


def test_fetch_events_success(monkeypatch):
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(
        200, {"events": [{"nom_fuite": "leak-1", "timestamp": "2025-01-01T00:00:00Z"}]}
    )
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [
        build_response(401),
        build_response(200, {"events": [{"nom_fuite": "leak-1"}]}),
    ]
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [build_response(401)] * 3
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client(x_restrict_access="token-xyz")
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": []})
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(500, text="server error")
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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

    client = make_client()
    client._session = MagicMock()
    client._session.post.side_effect = [build_response(429)] * 3
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": "nope"})
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

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
    client = make_client()

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
    client = make_client()
    client._session = MagicMock()
    client._session.post.return_value = build_response(200, {"events": []})
    client._rate_limiter = DummyLimiter()
    patch_get_token(client)

    results = asyncio.run(
        client.fetch_events(
            context="ctx",
            domain="example.com",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
    )
    assert results == []
