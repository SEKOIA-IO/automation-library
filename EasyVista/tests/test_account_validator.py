from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from easyvista.account_validator import EasyVistaAccountValidator

API_URL = "https://company.easyvista.com/api/v1/50004"
REQUESTS_URL = f"{API_URL}/requests"
ASSETS_URL = f"{API_URL}/assets"


def make_validator(**configuration):
    module = Module()
    module.configuration = {"base_url": "https://company.easyvista.com", "tenant_id": "50004", **configuration}
    validator = EasyVistaAccountValidator(module=module)
    validator.log = Mock()
    validator.error = Mock()
    return validator


@pytest.fixture
def validator():
    return make_validator(token="token")


def test_validate_with_token(validator, requests_mock):
    mock = requests_mock.get(REQUESTS_URL, json={"records": []})

    assert validator.validate() is True
    assert mock.last_request.headers["Authorization"] == "Bearer token"
    assert mock.last_request.qs["max_rows"] == ["1"]


def test_validate_with_basic_auth_and_ssl_verification_disabled(requests_mock):
    validator = make_validator(use_token=False, username="user", password="secret", verify_ssl=False)
    mock = requests_mock.get(REQUESTS_URL, json={"records": []})

    assert validator.validate() is True
    assert mock.last_request.headers["Authorization"].startswith("Basic ")
    assert mock.last_request.verify is False


@pytest.mark.parametrize(
    "configuration, message",
    [
        ({}, "`token` is required"),
        ({"use_token": False, "username": "user"}, "`username` and `password` are required"),
    ],
)
def test_validate_missing_credentials(requests_mock, configuration, message):
    validator = make_validator(**configuration)

    assert validator.validate() is False
    assert message in validator.error.call_args.args[0]
    assert not requests_mock.called


def test_validate_falls_back_on_assets_when_requests_are_forbidden(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, status_code=403, json={"error": "Forbidden"})
    requests_mock.get(ASSETS_URL, json={"records": []})

    assert validator.validate() is True


def test_validate_fails_when_every_route_is_forbidden(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, status_code=403, json={"error": "Forbidden"})
    requests_mock.get(ASSETS_URL, status_code=403, json={"error": "Forbidden"})

    assert validator.validate() is False
    assert "HTTP 403: Forbidden on GET /assets" in validator.error.call_args.args[0]


def test_validate_invalid_token(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, status_code=401, json={"error": "Invalid Login / Password"})
    assets = requests_mock.get(ASSETS_URL, json={"records": []})

    assert validator.validate() is False
    assert "Authentication failed" in validator.error.call_args.args[0]
    assert not assets.called


def test_validate_business_error_in_body(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, status_code=590, json={"error": "Bad Request"})

    assert validator.validate() is False
    assert "HTTP 590: Bad Request" in validator.error.call_args.args[0]


def test_validate_non_json_error(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, status_code=503, text="Service unavailable")

    assert validator.validate() is False
    assert "HTTP 503: Service unavailable" in validator.error.call_args.args[0]


def test_validate_connection_error(validator, requests_mock):
    requests_mock.get(REQUESTS_URL, exc=requests.ConnectionError)

    assert validator.validate() is False
    validator.error.assert_called_once()
