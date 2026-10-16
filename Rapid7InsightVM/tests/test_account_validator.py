from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from rapid7_insightvm.account_validator import Rapid7InsightVMAccountValidator

BASE_URL = "https://insightvm.example.com:3780"
ASSETS_URL = f"{BASE_URL}/api/3/assets"
VULNERABILITIES_URL = f"{BASE_URL}/api/3/vulnerabilities"
SEARCH_URL = f"{BASE_URL}/api/3/assets/search"

EMPTY_PAGE = {"resources": [], "page": {"number": 0, "size": 1, "totalPages": 0, "totalResources": 0}}


@pytest.fixture
def account_validator():
    module = Module()
    module.configuration = {
        "base_url": f"{BASE_URL}/",
        "username": "fake_user",
        "password": "fake_password",
    }
    validator = Rapid7InsightVMAccountValidator(module=module)
    validator.log = Mock()
    validator.log_exception = Mock()
    validator.error = Mock()
    yield validator


def error_message(validator) -> str:
    validator.error.assert_called_once()
    return validator.error.call_args.args[0]


def mock_all_ok(requests_mock):
    return (
        requests_mock.get(ASSETS_URL, json=EMPTY_PAGE),
        requests_mock.get(VULNERABILITIES_URL, json=EMPTY_PAGE),
        requests_mock.post(SEARCH_URL, json=EMPTY_PAGE),
    )


def test_validate_success(account_validator, requests_mock):
    assets, vulnerabilities, search = mock_all_ok(requests_mock)

    assert account_validator.validate() is True
    for probe in (assets, vulnerabilities, search):
        assert probe.call_count == 1
        assert probe.last_request.qs == {"page": ["0"], "size": ["1"]}
        assert probe.last_request.headers["Authorization"].startswith("Basic ")
    assert search.last_request.json() == {
        "match": "all",
        "filters": [{"field": "last-scan-date", "operator": "is-within-the-last", "value": 1}],
    }
    account_validator.error.assert_not_called()


def test_validate_invalid_credentials(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, status_code=401, json={"status": 401, "message": "Unauthorized"})

    assert account_validator.validate() is False
    message = error_message(account_validator)
    assert "Invalid InsightVM credentials (401)" in message
    assert "Unauthorized" in message


def test_validate_missing_permission(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, json=EMPTY_PAGE)
    requests_mock.get(VULNERABILITIES_URL, status_code=404, json={"status": 404, "message": "Not Found"})

    assert account_validator.validate() is False
    message = error_message(account_validator)
    assert "not allowed to read" in message
    assert VULNERABILITIES_URL in message


def test_validate_search_failure(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, json=EMPTY_PAGE)
    requests_mock.get(VULNERABILITIES_URL, json=EMPTY_PAGE)
    requests_mock.post(SEARCH_URL, status_code=400, text="Bad request")

    assert account_validator.validate() is False
    assert "Client error (400)" in error_message(account_validator)


def test_validate_server_error(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, status_code=500, json={"status": 500, "message": "Internal error"})

    assert account_validator.validate() is False
    assert "Server error (500)" in error_message(account_validator)


def test_validate_unexpected_status(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, status_code=302, text="")

    assert account_validator.validate() is False
    assert "Unexpected status (302)" in error_message(account_validator)


def test_validate_ssl_error(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=requests.exceptions.SSLError("certificate verify failed"))

    assert account_validator.validate() is False
    assert "verify_certificate" in error_message(account_validator)


def test_validate_connection_error(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=requests.ConnectionError("Connection refused"))

    assert account_validator.validate() is False
    assert "port (3780" in error_message(account_validator)


def test_validate_timeout(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=requests.Timeout)

    assert account_validator.validate() is False
    assert "Timeout" in error_message(account_validator)


def test_validate_network_error(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=requests.exceptions.TooManyRedirects("loop"))

    assert account_validator.validate() is False
    assert "Network error" in error_message(account_validator)


def test_validate_unexpected_error(account_validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=RuntimeError("boom"))

    assert account_validator.validate() is False
    assert "Unexpected error" in error_message(account_validator)


def test_client_honours_verify_certificate(account_validator):
    assert account_validator.client.verify is True
    assert account_validator.client.base_url == BASE_URL

    module = Module()
    module.configuration = {
        "base_url": BASE_URL,
        "username": "fake_user",
        "password": "fake_password",
        "verify_certificate": False,
    }
    assert Rapid7InsightVMAccountValidator(module=module).client.verify is False
