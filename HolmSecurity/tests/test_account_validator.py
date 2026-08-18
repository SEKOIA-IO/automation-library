from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from holm_security.account_validator import HolmSecurityAccountValidator

BASE_URL = "https://se-api.holmsecurity.com"
DEVICES_URL = f"{BASE_URL}/v2/devices"
NET_ASSETS_URL = f"{BASE_URL}/v2/net-assets"


@pytest.fixture
def account_validator():
    module = Module()
    module.configuration = {
        "base_url": BASE_URL,
        "api_token": "fake_api_token",
    }
    validator = HolmSecurityAccountValidator(module=module)
    validator.log = Mock()
    validator.log_exception = Mock()
    yield validator


def test_validate_success(account_validator, requests_mock):
    devices = requests_mock.get(DEVICES_URL, json={"count": 1, "results": []}, status_code=200)
    net_assets = requests_mock.get(NET_ASSETS_URL, json={"count": 1, "results": []}, status_code=200)

    assert account_validator.validate() is True
    # The Holm API paginates with `limit`; `page_size` is silently ignored.
    assert devices.last_request.qs.get("limit") == ["1"]
    assert devices.last_request.qs.get("page_size") is None
    assert net_assets.last_request.qs.get("limit") == ["1"]


def test_validate_devices_authentication_failure(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, json={"detail": "Invalid token."}, status_code=401)
    requests_mock.get(NET_ASSETS_URL, json={"count": 1, "results": []}, status_code=200)

    assert account_validator.validate() is False


def test_validate_net_assets_failure(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, json={"count": 1, "results": []}, status_code=200)
    requests_mock.get(NET_ASSETS_URL, json={"detail": "Forbidden"}, status_code=403)

    assert account_validator.validate() is False


def test_validate_server_error(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, json={"detail": "Internal error"}, status_code=500)

    assert account_validator.validate() is False


def test_validate_timeout(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, exc=requests.Timeout)

    assert account_validator.validate() is False


def test_validate_connection_error(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, exc=requests.ConnectionError)

    assert account_validator.validate() is False


def test_validate_unexpected_error(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, exc=ValueError("boom"))

    assert account_validator.validate() is False


def test_validate_non_json_error_body(account_validator, requests_mock):
    requests_mock.get(DEVICES_URL, text="Forbidden", status_code=403)

    assert account_validator.validate() is False
