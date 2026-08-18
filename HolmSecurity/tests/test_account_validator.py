from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from holm_security.account_validator import HolmSecurityAccountValidator

VALIDATION_URL = "https://se-api.holmsecurity.com/v2/devices"


@pytest.fixture
def account_validator():
    module = Module()
    module.configuration = {
        "base_url": "https://se-api.holmsecurity.com",
        "api_token": "fake_api_token",
    }
    validator = HolmSecurityAccountValidator(module=module)
    validator.log = Mock()
    validator.log_exception = Mock()
    yield validator


def test_validate_success(account_validator, requests_mock):
    matcher = requests_mock.get(VALIDATION_URL, json={"count": 1, "results": []}, status_code=200)

    assert account_validator.validate() is True
    # Ping call must use page_size=1
    assert matcher.last_request.qs.get("page_size") == ["1"]


def test_validate_authentication_failure(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, json={"detail": "Invalid token."}, status_code=401)

    assert account_validator.validate() is False


def test_validate_server_error(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, json={"detail": "Internal error"}, status_code=500)

    assert account_validator.validate() is False


def test_validate_timeout(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, exc=requests.Timeout)

    assert account_validator.validate() is False


def test_validate_connection_error(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, exc=requests.ConnectionError)

    assert account_validator.validate() is False


def test_validate_unexpected_error(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, exc=ValueError("boom"))

    assert account_validator.validate() is False


def test_validate_non_json_error_body(account_validator, requests_mock):
    requests_mock.get(VALIDATION_URL, text="Forbidden", status_code=403)

    assert account_validator.validate() is False
