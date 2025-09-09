import pytest
from unittest.mock import Mock

import requests

from tenable_conn import TenableModule
from tenable_conn.account_validator import TenableAccountValidator


@pytest.fixture
def tenable_account_validator():

    module = TenableModule()
    module.configuration = {
        "base_url": "http://example.com",
        "access_key": "fake_access_key",
        "secret_key": "fake_secret_key",
    }
    tenable_validator = TenableAccountValidator(module=module)

    tenable_validator.log = Mock()
    tenable_validator.log_exception = Mock()

    yield tenable_validator


def test_validate_success(tenable_account_validator, requests_mock):
    requests_mock.post(
        "http://example.com/vulns/export",
        json={"export_uuid": "fake_export_uuid"},
        status_code=200,
    )

    assert tenable_account_validator.validate() is True


def test_validate_ssl_error(tenable_account_validator, requests_mock):
    requests_mock.post(
        "http://example.com/vulns/export",
        exc=requests.exceptions.SSLError,
    )

    assert tenable_account_validator.validate() is False


def test_validate_unauthorized(tenable_account_validator, requests_mock):
    requests_mock.post(
        "http://example.com/vulns/export",
        status_code=401,
    )

    assert tenable_account_validator.validate() is False


def test_validate_access_key_error(tenable_account_validator, requests_mock):
    requests_mock.post(
        "http://example.com/vulns/export",
        status_code=403,
    )

    assert tenable_account_validator.validate() is False
