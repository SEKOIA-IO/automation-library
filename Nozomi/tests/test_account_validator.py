from unittest.mock import Mock

import pytest
import requests_mock

from nozomi_networks import NozomiConfiguration, NozomiModule
from nozomi_networks.account_validator import NozomiAccountValidator

BASE_URL = "https://guardian.test"
SIGN_IN_URL = f"{BASE_URL}/api/open/sign_in"


@pytest.fixture
def validator(symphony_storage):
    module = NozomiModule()
    module.configuration = NozomiConfiguration(
        key_name="fake_key_name",
        key_token="fake_key_token",
        base_url=BASE_URL,
    )
    validator = NozomiAccountValidator(module=module, data_path=symphony_storage)
    validator.error = Mock()
    return validator


def test_validator_configuration(validator):
    assert validator.module.configuration.key_name == "fake_key_name"
    assert validator.module.configuration.key_token == "fake_key_token"
    assert validator.module.configuration.base_url == BASE_URL


def test_validate_success(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        result = validator.validate()

    assert result is True
    validator.error.assert_not_called()


def test_validate_failure_bad_credentials(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=403, text="forbidden")
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()


def test_validate_failure_missing_access_token(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"token_type": "Bearer"})
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()


def test_validate_failure_connection_error(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, exc=ConnectionError("boom"))
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
