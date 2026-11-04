from unittest.mock import Mock

import pytest
import requests
from sekoia_automation.module import Module

from easyvista.account_validator import EasyVistaAccountValidator

ASSETS_URL = "https://company.easyvista.com/api/v1/50004/assets"


@pytest.fixture
def validator():
    module = Module()
    module.configuration = {"base_url": "https://company.easyvista.com", "account": "50004", "api_token": "token"}
    validator = EasyVistaAccountValidator(module=module)
    validator.log = Mock()
    validator.error = Mock()
    return validator


def test_validate_success(validator, requests_mock):
    mock = requests_mock.get(ASSETS_URL, json={"records": []})

    assert validator.validate() is True
    assert mock.last_request.headers["Authorization"] == "Bearer token"
    assert mock.last_request.qs["max_rows"] == ["1"]


def test_validate_invalid_token(validator, requests_mock):
    requests_mock.get(ASSETS_URL, status_code=401, json={"error": "Invalid Login/Password"})

    assert validator.validate() is False
    assert "401" in validator.error.call_args.args[0]


def test_validate_connection_error(validator, requests_mock):
    requests_mock.get(ASSETS_URL, exc=requests.ConnectionError)

    assert validator.validate() is False
    validator.error.assert_called_once()


def test_validate_server_error_reports_status(validator, requests_mock):
    requests_mock.get(ASSETS_URL, status_code=503, text="Service unavailable")

    assert validator.validate() is False
    assert "HTTP 503" in validator.error.call_args.args[0]
