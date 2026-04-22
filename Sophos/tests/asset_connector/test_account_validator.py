"""
Unit tests for SophosAccountValidator (sophos_module/account_validator.py).
"""
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

from sophos_module.base import SophosModule
from sophos_module.account_validator import SophosAccountValidator
from sophos_module.client.exceptions import SophosApiAuthenticationError

AUTH_URL = "https://id.sophos.com/api/v2/oauth2/token"
API_HOST = "https://api.central.sophos.com"



@pytest.fixture
def validator(symphony_storage):
    module = SophosModule()
    v = SophosAccountValidator(module=module, data_path=symphony_storage)
    v.module.configuration = {
        "oauth2_authorization_url": AUTH_URL,
        "api_host": API_HOST,
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }
    v.log = MagicMock()
    v.log_exception = MagicMock()
    v.error = MagicMock()
    return v


def _make_credentials(access_token: str = "valid_token", tenancy_type: str = "tenant", tenancy_id: str = "t-123"):
    creds = MagicMock()
    creds.access_token = access_token
    creds.tenancy_type = tenancy_type
    creds.tenancy_id = tenancy_id
    return creds


class TestValidateSuccess:
    def test_returns_true_on_valid_credentials(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.return_value = _make_credentials()

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is True
        validator.log.assert_called()

    def test_logs_tenancy_info(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.return_value = _make_credentials(tenancy_type="organization", tenancy_id="org-99")

        with patch.object(validator, "auth_client", mock_auth):
            validator.validate()

        log_calls = " ".join(str(c) for c in validator.log.call_args_list)
        assert "org-99" in log_calls or "organization" in log_calls


class TestValidateNoToken:
    def test_returns_false_when_no_access_token(self, validator):
        creds = _make_credentials(access_token=None)
        mock_auth = MagicMock()
        mock_auth.get_credentials.return_value = creds

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False
        validator.error.assert_called()

    def test_returns_false_when_credentials_none(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.return_value = None

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False


class TestValidateExceptions:
    def test_returns_false_on_authentication_error(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.side_effect = SophosApiAuthenticationError("Bad credentials")

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False
        validator.error.assert_called()

    def test_returns_false_on_http_error(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.side_effect = requests.HTTPError("503 Service Unavailable")

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False
        validator.error.assert_called()

    def test_returns_false_on_request_exception(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.side_effect = requests.ConnectionError("Network unreachable")

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False
        validator.error.assert_called()

    def test_returns_false_on_unexpected_exception(self, validator):
        mock_auth = MagicMock()
        mock_auth.get_credentials.side_effect = RuntimeError("Unexpected")

        with patch.object(validator, "auth_client", mock_auth):
            result = validator.validate()

        assert result is False
        validator.error.assert_called()
        validator.log_exception.assert_called()


class TestBuildAuth:
    def test_build_auth_uses_configuration(self, validator):
        """_build_auth should forward module configuration fields."""
        from sophos_module.client.auth import SophosApiAuthentication

        auth = validator._build_auth()
        assert isinstance(auth, SophosApiAuthentication)

