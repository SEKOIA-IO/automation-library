from unittest.mock import Mock, patch

import pytest

from office365.message_trace.client.auth import (
    ApiKeyAuthentication,
    AuthenticationError,
    format_authentication_error,
)

SCOPES = ["https://graph.microsoft.com/.default"]


@pytest.fixture
def msal_app():
    with patch("office365.message_trace.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        yield mock_msal.return_value


@pytest.fixture
def authentication(msal_app):
    return ApiKeyAuthentication(
        base_url="https://login.windows.net",
        tenant_id="/my-tenant",
        client_id="client_id",
        client_secret="client_secret",
        scopes=SCOPES,
    )


@pytest.mark.parametrize("result", [None, {"error": "invalid_client"}])
def test_authentication_error(result):
    error = AuthenticationError("Authentication failed", result=result)

    assert str(error) == "Authentication failed"
    assert error.result == result


def test_authority_is_built_from_base_url_and_tenant_id():
    with patch("office365.message_trace.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        ApiKeyAuthentication("https://login.windows.net", "/my-tenant", "client_id", "client_secret", SCOPES)

    mock_msal.assert_called_once_with(
        "client_id", authority="https://login.windows.net/my-tenant", client_credential="client_secret"
    )


@pytest.mark.parametrize(
    "silent_result,client_result,expected_token",
    [
        pytest.param({"access_token": "cached"}, None, "cached", id="token_from_cache"),
        pytest.param(None, {"access_token": "fresh"}, "fresh", id="token_from_client_credentials"),
    ],
)
def test_access_token(authentication, msal_app, silent_result, client_result, expected_token):
    msal_app.acquire_token_silent.return_value = silent_result
    msal_app.acquire_token_for_client.return_value = client_result

    assert authentication.access_token == expected_token
    msal_app.acquire_token_silent.assert_called_once_with(scopes=SCOPES, account=None)


def test_access_token_failure(authentication, msal_app):
    msal_app.acquire_token_silent.return_value = None
    msal_app.acquire_token_for_client.return_value = {"error": "invalid_client"}

    with pytest.raises(AuthenticationError) as exc_info:
        _ = authentication.access_token

    assert exc_info.value.result == {"error": "invalid_client"}
    assert "check your client ID, client secret and tenant ID" in str(exc_info.value)


def test_call_sets_bearer_header(authentication, msal_app):
    msal_app.acquire_token_silent.return_value = {"access_token": "TOKEN"}
    request = Mock(headers={})

    assert authentication(request) is request
    assert request.headers["Authorization"] == "Bearer TOKEN"


@pytest.mark.parametrize(
    "result,expected",
    [
        pytest.param(
            {"error": "invalid_client", "error_description": "Bad secret", "correlation_id": "42"},
            "Error: invalid_client - Description: Bad secret - Correlation ID: 42",
            id="full_result",
        ),
        pytest.param({}, "Error: None - Description: None - Correlation ID: None", id="empty_result"),
    ],
)
def test_format_authentication_error(result, expected):
    assert format_authentication_error(result) == expected
