from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from harfanglab.account_validator import HarfanglabAccountValidator


@pytest.fixture
def harfanglab_account_validator():

    module = Module()
    module.configuration = {
        "url": "http://example.com",
        "api_token": "fake_api_key",
    }
    harfanglab_validator = HarfanglabAccountValidator(module=module)

    harfanglab_validator.log = Mock()
    harfanglab_validator.log_exception = Mock()

    yield harfanglab_validator


def test_validate_success(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        json={"username": "test_user"},
        status_code=200,
    )

    assert harfanglab_account_validator.validate() is True


def test_validate_failure(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        json={"detail": "Invalid credentials"},
        status_code=401,
    )

    assert harfanglab_account_validator.validate() is False


def test_validate_unexpected_status(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        json={"detail": "Unexpected error"},
        status_code=500,
    )

    assert harfanglab_account_validator.validate() is False


def test_check_timeout(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        exc=requests.Timeout,
    )

    assert harfanglab_account_validator.validate() is False


def test_check_connection_error(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        exc=requests.ConnectionError,
    )

    assert harfanglab_account_validator.validate() is False


def test_check_unexpected_error(harfanglab_account_validator, requests_mock):
    requests_mock.get(
        "https://example.com/api/auth/users/me",
        exc=Exception("Unexpected error"),
    )

    assert harfanglab_account_validator.validate() is False
