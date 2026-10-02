from unittest.mock import MagicMock, patch

from flareio_modules import FlareIOModule
from flareio_modules.account_validator import FlareAccountValidator
from flareio_modules.models import FlareIOModuleConfiguration


def _build_validator() -> FlareAccountValidator:
    module = FlareIOModule()
    module.configuration = FlareIOModuleConfiguration(api_key="fw_test_key", tenant_id=42)
    validator = FlareAccountValidator(module=module)
    validator.log = MagicMock()
    return validator


@patch("flareio_modules.account_validator.FlareApiClient")
def test_validate_account_success(mock_client_cls):
    validator = _build_validator()

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    assert validator.validate() is True
    mock_client.get.assert_called_once_with("/tokens/test")


@patch("flareio_modules.account_validator.FlareApiClient")
def test_validate_account_failure_status(mock_client_cls):
    validator = _build_validator()

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    assert validator.validate() is False
    validator.log.assert_called()


@patch("flareio_modules.account_validator.FlareApiClient")
def test_validate_account_failure_exception(mock_client_cls):
    validator = _build_validator()

    mock_client = MagicMock()
    mock_client.get.side_effect = RuntimeError("network error")
    mock_client_cls.return_value = mock_client

    assert validator.validate() is False
    validator.log.assert_called()
