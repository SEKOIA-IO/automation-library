from unittest.mock import Mock, patch

import pytest
import requests
from sekoia_automation.module import Module

from rapid7_insightvm.account_validator import Rapid7InsightVMAccountValidator

BASE_URL = "https://eu.api.insight.rapid7.com/vm/v4/integration"
ASSETS_URL = f"{BASE_URL}/assets"
VULNS_URL = f"{BASE_URL}/vulnerabilities"


@pytest.fixture
def validator(symphony_storage):
    module = Module()
    module.configuration = {"region": "eu", "api_key": "fake_api_key"}

    validator = Rapid7InsightVMAccountValidator(module=module, data_path=symphony_storage)
    validator.log = Mock()
    validator.error = Mock()
    yield validator


def mock_success(requests_mock):
    return (
        requests_mock.post(ASSETS_URL, json={"data": [], "metadata": {}, "links": []}),
        requests_mock.post(VULNS_URL, json={"data": [], "metadata": {}, "links": []}),
    )


def error_message(validator) -> str:
    validator.error.assert_called_once()
    return validator.error.call_args[0][0]


def test_validate_success(validator, requests_mock):
    assets, vulns = mock_success(requests_mock)

    assert validator.validate() is True

    validator.error.assert_not_called()
    for matcher in (assets, vulns):
        request = matcher.last_request
        assert request.qs == {"size": ["1"]}
        assert request.json() == {}
        assert request.headers["X-Api-Key"] == "fake_api_key"


def test_validate_builds_the_url_from_the_region(validator, requests_mock):
    validator.module.configuration = {"region": "us2", "api_key": "fake_api_key"}
    assets = requests_mock.post("https://us2.api.insight.rapid7.com/vm/v4/integration/assets", json={})
    requests_mock.post("https://us2.api.insight.rapid7.com/vm/v4/integration/vulnerabilities", json={})

    assert validator.validate() is True
    assert assets.called


def test_validate_invalid_api_key(validator, requests_mock):
    requests_mock.post(ASSETS_URL, status_code=401, json={"message": "Unauthorized"})

    assert validator.validate() is False

    message = error_message(validator)
    assert "Invalid API key, or API key from another region" in message
    assert "(eu)" in message
    assert ASSETS_URL in message
    validator.log.assert_any_call(message=message, level="error")


@pytest.mark.parametrize("status", [403, 404])
def test_validate_no_access_to_insightvm(validator, requests_mock, status):
    requests_mock.post(ASSETS_URL, json={})
    requests_mock.post(VULNS_URL, status_code=status, json={"message": "Forbidden"})

    assert validator.validate() is False

    message = error_message(validator)
    assert "has no access to InsightVM" in message
    assert f"({status} at {VULNS_URL})" in message


def test_validate_other_client_error(validator, requests_mock):
    requests_mock.post(ASSETS_URL, status_code=429, text="slow down")

    assert validator.validate() is False
    assert "Client error (429)" in error_message(validator)
    assert "slow down" in error_message(validator)


def test_validate_server_error(validator, requests_mock):
    requests_mock.post(ASSETS_URL, status_code=503, json=["unavailable"])

    assert validator.validate() is False
    assert "Server error (503)" in error_message(validator)


def test_validate_unexpected_status(validator, requests_mock):
    requests_mock.post(ASSETS_URL, status_code=302, json={})

    assert validator.validate() is False
    assert "Unexpected status (302)" in error_message(validator)


@pytest.mark.parametrize(
    "exception, expected",
    [
        (requests.Timeout("too slow"), "Timeout while validating"),
        (requests.ConnectionError("unreachable"), "Unable to reach the Insight Platform"),
        (requests.RequestException("broken"), "Network error while validating"),
        (ValueError("weird"), "Unexpected error while validating"),
    ],
)
def test_validate_request_failures(validator, exception, expected):
    with patch.object(validator.client, "request", side_effect=exception):
        assert validator.validate() is False

    message = error_message(validator)
    assert expected in message
    if isinstance(exception, requests.ConnectionError):
        assert "check the region (eu)" in message
