import pytest
import requests_mock

from zimperium_modules import ZimperiumModule
from zimperium_modules.account_validator import ZimperiumAccountValidator


@pytest.fixture
def account_validator(data_storage):
    module = ZimperiumModule()
    module.configuration = {
        "base_url": "https://example.com",
        "client_id": "CLIENT_ID",
        "client_secret": "CLIENT_SECRET",
    }
    validator = ZimperiumAccountValidator(module=module, data_path=data_storage)
    yield validator


def test_validate_success(account_validator):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.com/api/auth/v1/api_keys/login",
            status_code=200,
            json={"accessToken": "TOKEN1", "refreshToken": "TOKEN2"},
        )

        result = account_validator.validate()
        assert result is True


def test_validate_api_error_response(account_validator):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.com/api/auth/v1/api_keys/login",
            status_code=401,
        )

        result = account_validator.validate()
        assert result is False
