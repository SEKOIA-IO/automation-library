from unittest.mock import patch

import pytest
import requests_mock

from thor_cloud_modules import ThorCloudModule, client
from thor_cloud_modules.account_validator import ThorCloudAccountValidator
from thor_cloud_modules.models import ThorCloudModuleConfiguration

LITE = client.ENDPOINTS["thor_cloud_lite"] + client.SCAN_SEARCH_PATH
CLOUD = client.ENDPOINTS["thor_cloud"] + client.SCAN_SEARCH_PATH


@pytest.fixture
def validator(tmp_path):
    module = ThorCloudModule()
    module._configuration = ThorCloudModuleConfiguration(api_key="secret")
    return ThorCloudAccountValidator(module=module, data_path=tmp_path)


def test_valid_for_thor_cloud_lite(validator):
    with requests_mock.Mocker() as m:
        m.get(LITE, json={"data": [], "total": 0})
        m.get(CLOUD, status_code=401)
        assert validator.validate() is True
        assert m.request_history[0].headers["Authorization"] == "secret"


def test_valid_for_thor_cloud(validator):
    with requests_mock.Mocker() as m:
        m.get(LITE, status_code=401)
        m.get(CLOUD, json={"data": [], "total": 0})
        assert validator.validate() is True


def test_rejected_by_both_services(validator):
    with requests_mock.Mocker() as m:
        m.get(LITE, status_code=401)
        m.get(CLOUD, status_code=403)
        with patch.object(validator, "error") as error:
            assert validator.validate() is False
    message = error.call_args.args[0]
    assert "HTTP 401" in message and "HTTP 403" in message
    assert "secret" not in message


def test_network_error_is_reported(validator):
    with requests_mock.Mocker() as m:
        m.get(LITE, exc=client.requests.ConnectionError)
        m.get(CLOUD, exc=client.requests.ConnectTimeout)
        with patch.object(validator, "error") as error:
            assert validator.validate() is False
    assert "ConnectionError" in error.call_args.args[0]


def test_empty_api_key(validator):
    validator.module._configuration = ThorCloudModuleConfiguration(api_key="")
    with patch.object(validator, "error") as error:
        assert validator.validate() is False
    error.assert_called_once()
