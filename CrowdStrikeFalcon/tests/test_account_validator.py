import pytest
from unittest.mock import Mock

import requests


from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.account_validator import CrowdstrikeFalconAccountValidator


@pytest.fixture
def crowdstrike_account_validator():

    module = CrowdStrikeFalconModule()
    module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "client_id": "foo",
        "client_secret": "bar",
    }
    crowdstrike_validator = CrowdstrikeFalconAccountValidator(module=module)

    crowdstrike_validator.log = Mock()
    crowdstrike_validator.log_exception = Mock()

    yield crowdstrike_validator


def test_validate_success(crowdstrike_account_validator, requests_mock):
    requests_mock.post(
        "https://my.fake.sekoia/oauth2/token",
        json={
            "access_token": "fake_token",
            "token_type": "bearer",
            "expires_in": 299,
        },
        status_code=200,
    )

    assert crowdstrike_account_validator.validate() is True


def test_validate_failure(crowdstrike_account_validator, requests_mock):
    requests_mock.get(
        "https://my.fake.sekoia/oauth2/token",
        json={},
        status_code=401,
    )

    assert crowdstrike_account_validator.validate() is False


def test_validate_unexpected_status(crowdstrike_account_validator, requests_mock):
    requests_mock.get(
        "https://my.fake.sekoia/oauth2/token",
        json={},
        status_code=500,
    )

    assert crowdstrike_account_validator.validate() is False


def test_check_timeout(crowdstrike_account_validator, requests_mock):
    requests_mock.get(
        "https://my.fake.sekoia/api/",
        exc=requests.Timeout,
    )

    assert crowdstrike_account_validator.validate() is False


def test_check_connection_error(crowdstrike_account_validator, requests_mock):
    requests_mock.get(
        "https://my.fake.sekoia/api/",
        exc=requests.ConnectionError,
    )

    assert crowdstrike_account_validator.validate() is False


def test_check_unexpected_error(crowdstrike_account_validator, requests_mock):
    requests_mock.get(
        "https://my.fake.sekoia/api/",
        exc=Exception("Unexpected error"),
    )

    assert crowdstrike_account_validator.validate() is False
