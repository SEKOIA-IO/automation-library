from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock, patch

from pyrate_limiter import Duration, Limiter, RequestRate

from mimecast_modules.client.auth import ApiKeyAuthentication, MimecastCredentials


def test_mimecast_credentials_authorization() -> None:
    credentials = MimecastCredentials()
    credentials.token_type = "bearer"
    credentials.access_token = "token"

    assert credentials.authorization == "Bearer token"


def test_get_credentials_is_cached_until_expiry_window() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = ApiKeyAuthentication("id", "secret", limiter)

    response = Mock()
    response.json.return_value = {
        "token_type": "bearer",
        "access_token": "token-a",
        "expires_in": 1800,
    }
    response.raise_for_status.return_value = None

    auth_any = cast(Any, auth)
    auth_any._ApiKeyAuthentication__http_session.post = Mock(return_value=response)

    first = auth.get_credentials()
    second = auth.get_credentials()

    assert first.access_token == "token-a"
    assert second.access_token == "token-a"
    assert auth_any._ApiKeyAuthentication__http_session.post.call_count == 1


def test_get_credentials_refreshes_when_near_expiry() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = ApiKeyAuthentication("id", "secret", limiter)

    first_response = Mock()
    first_response.json.return_value = {
        "token_type": "bearer",
        "access_token": "token-a",
        "expires_in": 1800,
    }
    first_response.raise_for_status.return_value = None

    second_response = Mock()
    second_response.json.return_value = {
        "token_type": "bearer",
        "access_token": "token-b",
        "expires_in": 1800,
    }
    second_response.raise_for_status.return_value = None

    auth_any = cast(Any, auth)
    auth_any._ApiKeyAuthentication__http_session.post = Mock(side_effect=[first_response, second_response])

    first = auth.get_credentials()
    auth_any._ApiKeyAuthentication__credentials.expires_at = datetime.utcnow() + timedelta(seconds=120)
    refreshed = auth.get_credentials()

    assert first.access_token == "token-a"
    assert refreshed.access_token == "token-b"
    assert auth_any._ApiKeyAuthentication__http_session.post.call_count == 2


def test_auth_call_sets_authorization_header() -> None:
    limiter = Limiter(RequestRate(limit=50, interval=Duration.MINUTE))
    auth = ApiKeyAuthentication("id", "secret", limiter)

    credentials = MimecastCredentials()
    credentials.token_type = "bearer"
    credentials.access_token = "token"
    credentials.expires_at = datetime.utcnow() + timedelta(hours=1)

    request = Mock(headers={})
    with patch.object(auth, "get_credentials", return_value=credentials):
        returned = auth(request)

    assert returned is request
    assert request.headers["Authorization"] == "Bearer token"
