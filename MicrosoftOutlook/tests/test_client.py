from datetime import UTC, datetime, timedelta

import pytest
import requests

from microsoft_outlook_modules.client.auth import (
    GraphApiAuthentication,
    MicrosoftDefenderCredentials,
)
from microsoft_outlook_modules.client.retry import Retry


def test_credentials_authorization_title_cases_token_type():
    credentials = MicrosoftDefenderCredentials()
    credentials.token_type = "bearer"
    credentials.access_token = "sample-token"
    credentials.expires_at = datetime.now(UTC) + timedelta(seconds=600)

    assert credentials.authorization == "Bearer sample-token"


def test_graph_auth_fetches_and_reuses_cached_credentials(monkeypatch):
    auth = GraphApiAuthentication(
        app_id="sample-client-id",
        app_secret="sample-client-secret",
        tenant_id="sample-tenant-id",
        ratelimit_per_minute=45,
    )

    calls = {"count": 0}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "token_type": "bearer",
                "access_token": "sample-token",
                "expires_in": 3600,
            }

    def fake_get(url, data):
        calls["count"] += 1
        assert url == "https://login.microsoftonline.com/sample-tenant-id/oauth2/v2.0/token"
        assert data["client_id"] == "sample-client-id"
        return DummyResponse()

    monkeypatch.setattr(auth._GraphApiAuthentication__http_session, "get", fake_get)

    first_credentials = auth.get_credentials()
    second_credentials = auth.get_credentials()

    assert first_credentials.authorization == "Bearer sample-token"
    assert second_credentials.authorization == "Bearer sample-token"
    assert first_credentials is second_credentials
    assert calls["count"] == 1


def test_graph_auth_refreshes_expired_credentials(monkeypatch):
    auth = GraphApiAuthentication(
        app_id="sample-client-id",
        app_secret="sample-client-secret",
        tenant_id="sample-tenant-id",
        ratelimit_per_minute=45,
    )

    expired_credentials = MicrosoftDefenderCredentials()
    expired_credentials.token_type = "bearer"
    expired_credentials.access_token = "old-token"
    expired_credentials.expires_at = datetime.now(UTC) - timedelta(seconds=60)
    auth._GraphApiAuthentication__api_credentials = expired_credentials

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "token_type": "bearer",
                "access_token": "new-token",
                "expires_in": 3600,
            }

    monkeypatch.setattr(auth._GraphApiAuthentication__http_session, "get", lambda *_args, **_kwargs: DummyResponse())

    credentials = auth.get_credentials()
    assert credentials.authorization == "Bearer new-token"


def test_graph_auth_call_sets_request_authorization_header(monkeypatch):
    auth = GraphApiAuthentication(
        app_id="sample-client-id",
        app_secret="sample-client-secret",
        tenant_id="sample-tenant-id",
        ratelimit_per_minute=45,
    )

    credentials = MicrosoftDefenderCredentials()
    credentials.token_type = "bearer"
    credentials.access_token = "sample-token"
    credentials.expires_at = datetime.now(UTC) + timedelta(seconds=600)

    monkeypatch.setattr(auth, "get_credentials", lambda: credentials)

    request = requests.Request(method="GET", url="https://graph.microsoft.com/v1.0/me")
    prepared = request.prepare()

    auth(prepared)

    assert prepared.headers["Authorization"] == "Bearer sample-token"


@pytest.mark.parametrize(
    "offset_seconds,expect_positive_delay",
    [
        (120, True),
        (-120, False),
    ],
)
def test_retry_parse_ratelimit_retry_after(offset_seconds, expect_positive_delay):
    timestamp = str(datetime.now(UTC).timestamp() + offset_seconds)
    delay = Retry.parse_ratelimit_retry_after(timestamp)

    if expect_positive_delay:
        assert delay is not None
        assert delay > 0
    else:
        assert delay is None


@pytest.mark.parametrize(
    "retry_after_header,expected_delay",
    [
        ("5", 5),
        (None, None),
    ],
)
def test_retry_get_retry_after(retry_after_header, expected_delay):
    retry = Retry(total=3)

    class Response:
        @staticmethod
        def getheader(name):
            if name == "Retry-After":
                return retry_after_header
            return None

    assert retry.get_retry_after(Response()) == expected_delay


def test_graph_auth_get_credentials_raises_on_http_error(monkeypatch):
    auth = GraphApiAuthentication(
        app_id="sample-client-id",
        app_secret="sample-client-secret",
        tenant_id="sample-tenant-id",
        ratelimit_per_minute=45,
    )

    class DummyResponse:
        @staticmethod
        def raise_for_status():
            raise requests.HTTPError("token endpoint failure")

    monkeypatch.setattr(auth._GraphApiAuthentication__http_session, "get", lambda *_args, **_kwargs: DummyResponse())

    with pytest.raises(requests.HTTPError, match="token endpoint failure"):
        auth.get_credentials()
