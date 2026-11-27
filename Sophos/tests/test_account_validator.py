"""
Unit tests for SophosAccountValidator (sophos_module/account_validator.py).
"""

from unittest.mock import MagicMock

import pytest
import requests

from sophos_module.account_validator import SophosAccountValidator
from sophos_module.base import SophosModule
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosApiAuthenticationError

AUTH_URL = "https://id.sophos.com/api/v2/oauth2/token"
API_HOST = "https://api.central.sophos.com"


@pytest.fixture
def validator(symphony_storage):
    validator = SophosAccountValidator(module=SophosModule(), data_path=symphony_storage)
    validator.module.configuration = {
        "oauth2_authorization_url": AUTH_URL,
        "api_host": API_HOST,
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }
    validator.log = MagicMock()
    validator.log_exception = MagicMock()
    validator.error = MagicMock()
    # cached_property: replace the authentication by a mock
    validator.auth_client = MagicMock()
    return validator


def make_credentials(access_token: str | None = "valid_token", tenancy_type="tenant", tenancy_id="t-123"):
    credentials = MagicMock()
    credentials.access_token = access_token
    credentials.tenancy_type = tenancy_type
    credentials.tenancy_id = tenancy_id
    return credentials


@pytest.mark.parametrize(
    "tenancy_type, tenancy_id",
    [("tenant", "t-123"), ("organization", "org-99"), ("partner", "p-1")],
)
def test_validate_success(validator, tenancy_type, tenancy_id):
    validator.auth_client.get_credentials.return_value = make_credentials(
        tenancy_type=tenancy_type, tenancy_id=tenancy_id
    )

    assert validator.validate() is True

    validator.error.assert_not_called()
    assert validator.log.call_args_list[-1].args[0] == (
        f"Credentials validated - tenancy_type={tenancy_type}, tenancy_id={tenancy_id}"
    )


@pytest.mark.parametrize(
    "credentials",
    [pytest.param(None, id="no-credentials"), pytest.param(make_credentials(access_token=None), id="no-token")],
)
def test_validate_without_access_token(validator, credentials):
    validator.auth_client.get_credentials.return_value = credentials

    assert validator.validate() is False

    validator.error.assert_called_once_with("Failed to validate Sophos credentials: no access token returned")


def unauthorized_response() -> requests.Response:
    response = requests.Response()
    response.status_code = 401
    response.url = AUTH_URL
    response._content = b'{"error": "invalid_client", "message": "Bad client credentials"}'
    return response


@pytest.mark.parametrize(
    "error, expected_message",
    [
        pytest.param(
            SophosApiAuthenticationError("Bad credentials"),
            "Failed to validate Sophos credentials: Bad credentials",
            id="authentication-error",
        ),
        pytest.param(
            requests.HTTPError("503 Service Unavailable"),
            "Failed to validate Sophos credentials due to HTTP error: 503 Service Unavailable",
            id="http-error",
        ),
        pytest.param(
            requests.HTTPError("401 Client Error", response=unauthorized_response()),
            "Failed to validate Sophos credentials: status 401 - invalid_client: Bad client credentials"
            ". Check the client_id and client_secret of the module, and that the API credential has not expired",
            id="http-error-with-response",
        ),
        pytest.param(
            requests.ConnectionError("Network unreachable"),
            "Failed to validate Sophos credentials due to network error: Network unreachable",
            id="network-error",
        ),
        pytest.param(
            RuntimeError("Unexpected"),
            "Failed to validate Sophos credentials due to an unexpected error",
            id="unexpected-error",
        ),
    ],
)
def test_validate_errors(validator, error, expected_message):
    validator.auth_client.get_credentials.side_effect = error

    assert validator.validate() is False

    validator.error.assert_called_once_with(expected_message)
    assert validator.log_exception.call_count == isinstance(error, RuntimeError)


def test_auth_client_uses_the_module_configuration(symphony_storage):
    validator = SophosAccountValidator(module=SophosModule(), data_path=symphony_storage)
    validator.module.configuration = {
        "oauth2_authorization_url": AUTH_URL,
        "api_host": API_HOST,
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }

    auth = validator.auth_client

    assert isinstance(auth, SophosApiAuthentication)
    assert auth is validator.auth_client
    assert auth._SophosApiAuthentication__api_host == API_HOST
    assert auth._SophosApiAuthentication__authorization_url == AUTH_URL
    assert auth._SophosApiAuthentication__client_id == "test-client-id"
