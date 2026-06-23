from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
import requests_mock as requests_mock_module

from eset_modules import EsetModule
from eset_modules.account_validator import EsetAccountValidator
from eset_modules.models import EsetModuleConfiguration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator(data_storage):
    module = EsetModule()
    module.configuration = EsetModuleConfiguration(
        region="eu",
        username="testuser",
        password="testpassword",
    )
    v = EsetAccountValidator(module=module, data_path=data_storage)
    v.error = Mock()
    return v


@pytest.fixture
def mock_client(validator):
    """Inject a plain requests.Session as the client to avoid the real OAuth flow."""
    session = requests.Session()
    validator.__dict__["client"] = session
    return session


# ---------------------------------------------------------------------------
# Config sanity check
# ---------------------------------------------------------------------------


def test_validator_configuration(validator):
    assert validator.module.configuration.region == "eu"
    assert validator.module.configuration.username == "testuser"
    assert validator.module.configuration.password == "testpassword"


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_validate_success(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            status_code=200,
            json={"devices": [], "nextPageToken": None},
        )
        result = validator.validate()

    assert result is True
    validator.error.assert_not_called()


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_validate_failure_unauthorized(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            status_code=401,
        )
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
    error_msg = validator.error.call_args[0][0]
    assert "ESET EDR" in error_msg


def test_validate_failure_forbidden(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            status_code=403,
        )
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()


def test_validate_failure_server_error(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            status_code=500,
        )
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()


def test_validate_failure_connection_error(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            exc=requests.exceptions.ConnectionError("unreachable"),
        )
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
    error_msg = validator.error.call_args[0][0]
    assert "ESET EDR" in error_msg


def test_validate_failure_timeout(validator, mock_client):
    with requests_mock_module.Mocker() as m:
        m.get(
            "https://eu.automation.eset.systems/v1/devices",
            exc=requests.exceptions.Timeout("timed out"),
        )
        result = validator.validate()

    assert result is False
    validator.error.assert_called_once()
