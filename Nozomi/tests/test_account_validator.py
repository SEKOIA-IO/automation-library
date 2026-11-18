from unittest.mock import Mock

import pytest
import requests
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
        base_url=f"{BASE_URL}/",
    )
    validator = NozomiAccountValidator(module=module, data_path=symphony_storage)
    validator.error = Mock()
    validator.log = Mock()
    return validator


def test_validator_configuration(validator):
    assert validator.module.configuration.key_name == "fake_key_name"
    assert validator.module.configuration.key_token == "fake_key_token"
    assert validator.module.configuration.base_url == f"{BASE_URL}/"


def test_validate_success(validator):
    with requests_mock.Mocker() as m:
        sign_in = m.post(SIGN_IN_URL, status_code=200, json={"access_token": "xyz", "token_type": "Bearer"})
        result = validator.validate()

    assert result is True
    assert sign_in.last_request.json() == {"key_name": "fake_key_name", "key_token": "fake_key_token"}
    validator.error.assert_not_called()


@pytest.mark.parametrize("status_code", [401, 403])
def test_validate_failure_bad_credentials(validator, status_code):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=status_code, text="forbidden")
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
    message = validator.error.call_args.args[0]
    assert f"client error ({status_code}) at {SIGN_IN_URL}" in message
    validator.log.assert_any_call(message=message, level="error")


def test_validate_failure_server_error(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=503, text="unavailable")
        result = validator.validate()

    assert result is False
    assert "server error (503)" in validator.error.call_args.args[0]


def test_validate_failure_unexpected_status(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=302, text="redirect")
        result = validator.validate()

    assert result is False
    assert "unexpected response (302)" in validator.error.call_args.args[0]


def test_validate_failure_missing_access_token(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, status_code=200, json={"token_type": "Bearer"})
        result = validator.validate()

    assert result is False
    assert "access_token not found" in validator.error.call_args.args[0]


def test_validate_failure_timeout(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, exc=requests.exceptions.ConnectTimeout)
        result = validator.validate()

    assert result is False
    assert f"timeout at {SIGN_IN_URL}" in validator.error.call_args.args[0]


def test_validate_failure_network_error(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, exc=requests.exceptions.ConnectionError("boom"))
        result = validator.validate()

    assert result is False
    assert "network error" in validator.error.call_args.args[0]


def test_validate_failure_unexpected_error(validator):
    with requests_mock.Mocker() as m:
        m.post(SIGN_IN_URL, exc=ValueError("weird"))
        result = validator.validate()

    assert result is False
    assert "unexpected error" in validator.error.call_args.args[0]
