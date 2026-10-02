from unittest.mock import Mock, patch

import pytest
from google.auth.exceptions import RefreshError
from sekoia_automation.module import Module

from google_module.account_validator import CLOUD_PLATFORM_SCOPE, GoogleAccountValidator


@pytest.fixture
def validator(tmp_path, credentials):
    module = Module()
    module.configuration = {"credentials": credentials}
    validator = GoogleAccountValidator(module=module, data_path=tmp_path)
    validator.log = Mock()
    validator.error = Mock()
    return validator


def test_validate_success(validator, credentials):
    with patch("google_module.account_validator.service_account.Credentials") as credentials_class:
        assert validator.validate() is True

    credentials_class.from_service_account_info.assert_called_once_with(credentials, scopes=[CLOUD_PLATFORM_SCOPE])
    credentials_class.from_service_account_info.return_value.refresh.assert_called_once()
    validator.error.assert_not_called()


def test_validate_rejected_key(validator):
    with patch("google_module.account_validator.service_account.Credentials") as credentials_class:
        credentials_class.from_service_account_info.return_value.refresh.side_effect = RefreshError(
            "invalid_grant: Invalid grant: account not found"
        )
        assert validator.validate() is False

    validator.error.assert_called_once_with(
        "Invalid Google service account credentials: invalid_grant: Invalid grant: account not found"
    )


def test_validate_malformed_key(validator):
    assert validator.validate() is False

    assert validator.error.call_args.args[0].startswith("Invalid Google service account credentials: ")
