import pytest

from sophos_module.base import SophosModule


@pytest.fixture
def module(symphony_storage):
    module = SophosModule()
    module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": "https://api-eu.central.sophos.com",
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    return module


@pytest.fixture
def add_auth_mock():
    return _add_auth_mock


def _add_auth_mock(mock, host, module):
    mock.post(
        f"{module.configuration.oauth2_authorization_url}",
        status_code=200,
        json={
            "access_token": "access_token",
            "refresh_token": "refresh_token",
            "token_type": "bearer",
            "message": "OK",
            "errorCode": "success",
            "expires_in": 3600,
        },
    )

    mock.get(
        f"{module.configuration.api_host}/whoami/v1",
        status_code=200,
        json={
            "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
            "idType": "tenant",
            "apiHosts": {
                "global": "https://api.central.sophos.com",
                "dataRegion": host,
            },
        },
    )
