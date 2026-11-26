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

    def fake_get(url, data, timeout):
        assert timeout == (10, 30)
        calls["count"] += 1
        assert url == "https://login.microsoftonline.com/sample-tenant-id/oauth2/v2.0/token"
        assert data["client_id"] == "sample-client-id"
        return DummyResponse()

    monkeypatch.setattr(auth._GraphApiAuthentication__http_session, "post", fake_get)

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

    monkeypatch.setattr(
        auth._GraphApiAuthentication__http_session,
        "post",
        lambda *_args, **_kwargs: DummyResponse(),
    )

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

    monkeypatch.setattr(
        auth._GraphApiAuthentication__http_session,
        "post",
        lambda *_args, **_kwargs: DummyResponse(),
    )

    with pytest.raises(requests.HTTPError, match="token endpoint failure"):
        auth.get_credentials()


def test_long_retry_after_preserves_deadline_without_sleeping():
    from unittest.mock import patch

    from urllib3.response import HTTPResponse

    from microsoft_outlook_modules.client.retry import RetryDelayExceeded
    from microsoft_outlook_modules.errors import describe_error

    with patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100):
        with pytest.raises(RetryDelayExceeded) as caught:
            Retry().get_retry_after(HTTPResponse(headers={"Retry-After": "3600"}))
    assert caught.value.retry_at == 3700
    assert describe_error(caught.value)["retryable"] is True
    assert describe_error(caught.value)["code"] == "retry_delay_exceeded"


@pytest.mark.parametrize("header,expected", [("3600", 3700), ("10", 110), ("0", None), ("bad", None), (None, None)])
def test_retry_deadline_from_unretried_http_response(header, expected):
    from unittest.mock import patch

    from microsoft_outlook_modules.client.retry import retry_deadline

    response = requests.Response()
    response.status_code = 503
    if header is not None:
        response.headers["Retry-After"] = header
    with patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100):
        assert retry_deadline(requests.HTTPError(response=response)) == expected
    response.status_code = 401
    assert retry_deadline(requests.HTTPError(response=response)) is None
    assert retry_deadline(requests.Timeout()) is None
    assert retry_deadline(requests.HTTPError()) is None


@pytest.mark.parametrize("status", [429, 503])
def test_token_response_preserves_retry_after_and_transient_classification(requests_mock, status):
    from microsoft_outlook_modules.client.retry import retry_deadline
    from microsoft_outlook_modules.errors import describe_error

    auth = GraphApiAuthentication(app_id="id", app_secret="fake", tenant_id="tenant", ratelimit_per_minute=45)
    requests_mock.post(
        "https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
        status_code=status,
        headers={"Retry-After": "3600"},
    )
    with pytest.raises(requests.HTTPError) as caught:
        auth.get_credentials()
    assert retry_deadline(caught.value) is not None
    assert describe_error(caught.value)["retryable"] is True


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH"])
@pytest.mark.parametrize("status", [429, 503])
def test_real_http_adapter_preserves_backoff_through_requests_wrapping(method, status):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from time import monotonic

    from requests.adapters import HTTPAdapter

    from microsoft_outlook_modules.client.retry import retry_deadline

    class Handler(BaseHTTPRequestHandler):
        calls = 0

        def respond(self):
            Handler.calls += 1
            self.send_response(status)
            self.send_header("Retry-After", "3600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_GET = respond  # noqa: N815 - method names required by BaseHTTPRequestHandler
        do_POST = respond  # noqa: N815
        do_PATCH = respond  # noqa: N815

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        with requests.Session() as session:
            session.trust_env = False
            session.mount(
                "http://",
                HTTPAdapter(
                    max_retries=Retry(
                        total=2, status_forcelist=[429, 503], allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"})
                    )
                ),
            )
            with pytest.raises(requests.RequestException) as caught:
                response = session.request(method, f"http://127.0.0.1:{server.server_port}/", timeout=2)
                response.raise_for_status()
            deadline = retry_deadline(caught.value)
            assert deadline is not None and deadline - monotonic() > 3590
            assert Handler.calls == 1
            if method == "GET":
                assert isinstance(caught.value, requests.ConnectionError)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
