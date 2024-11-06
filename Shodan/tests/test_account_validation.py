import pytest

from shodan import AccountValidation


@pytest.fixture
def validation():
    validation = AccountValidation()
    validation.module.configuration = {
        "base_url": "https://api.shodan.io",
        "api_key": "foo",
    }
    return validation


def test_account_validation_success(validation, requests_mock):
    requests_mock.get("https://api.shodan.io/account/profile?key=foo", json={"success": True})
    res = validation.validate()
    assert res is True


def test_account_validation_failure(validation, requests_mock):
    requests_mock.get("https://api.shodan.io/account/profile?key=foo", status_code=401)
    res = validation.validate()
    assert res is False
