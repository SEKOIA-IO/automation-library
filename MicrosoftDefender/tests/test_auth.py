from urllib.parse import parse_qs

import requests_mock

from microsoftdefender_modules.client.auth import ApiKeyAuthentication


def _token_response() -> dict:
    return {
        "token_type": "bearer",
        "access_token": "foo-token",
        "expires_in": 1799,
    }


def _request_form(request) -> dict:
    return {key: value[0] for key, value in parse_qs(request.text).items()}


def test_token_request_uses_default_resource():
    auth = ApiKeyAuthentication(
        app_id="app",
        app_secret="secret",
        tenant_id="tenant",
        ratelimit_per_minute=45,
    )

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/tenant/oauth2/token",
            json=_token_response(),
        )

        auth.get_credentials()

        assert _request_form(mock.last_request)["resource"] == "https://api.securitycenter.microsoft.com"


def test_token_request_uses_configured_base_url():
    auth = ApiKeyAuthentication(
        app_id="app",
        app_secret="secret",
        tenant_id="tenant",
        ratelimit_per_minute=45,
        base_url="https://eu.api.security.microsoft.com",
    )

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/tenant/oauth2/token",
            json=_token_response(),
        )

        auth.get_credentials()

        assert _request_form(mock.last_request)["resource"] == "https://eu.api.security.microsoft.com"


def test_token_request_strips_trailing_slash():
    auth = ApiKeyAuthentication(
        app_id="app",
        app_secret="secret",
        tenant_id="tenant",
        ratelimit_per_minute=45,
        base_url="https://api-eu.securitycenter.microsoft.com/",
    )

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/tenant/oauth2/token",
            json=_token_response(),
        )

        auth.get_credentials()

        assert _request_form(mock.last_request)["resource"] == "https://api-eu.securitycenter.microsoft.com"
