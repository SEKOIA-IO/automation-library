from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from microsoftdefender_modules.account_validator import MicrosoftDefenderAccountValidator


@pytest.fixture
def validator(data_storage):
    module = Module()
    module.configuration = {
        "base_url": "https://api.securitycenter.microsoft.com",
        "app_id": "fake_app_id",
        "app_secret": "fake_app_secret",
        "tenant_id": "fake_tenant_id",
    }
    validator = MicrosoftDefenderAccountValidator(module=module, data_path=data_storage)
    validator.error = Mock()
    return validator


def test_validator_has_expected_config(validator):
    assert validator.module.configuration["app_id"] == "fake_app_id"
    assert validator.module.configuration["app_secret"] == "fake_app_secret"
    assert validator.module.configuration["tenant_id"] == "fake_tenant_id"


def test_validate_success(validator):
    mock_client = Mock()
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_client.get.return_value = mock_response
    mock_client.base_url = "https://api.securitycenter.microsoft.com"
    validator.client = mock_client

    result = validator.validate()

    assert result is True
    validator.error.assert_not_called()


def test_validate_failure_http_error(validator):
    mock_client = Mock()
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    mock_client.get.return_value = mock_response
    mock_client.base_url = "https://api.securitycenter.microsoft.com"
    validator.client = mock_client

    result = validator.validate()

    assert result is False
    validator.error.assert_called_once()


def test_validate_failure_connection_error(validator):
    mock_client = Mock()
    mock_client.get.side_effect = requests.ConnectionError("Connection refused")
    mock_client.base_url = "https://api.securitycenter.microsoft.com"
    validator.client = mock_client

    result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
