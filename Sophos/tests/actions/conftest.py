import pytest
import requests_mock

from sophos_module.base import SophosModule

API_HOST = "https://api-eu.central.sophos.com"
DATA_REGION = "https://api-eu01.central.sophos.com"
ENDPOINT_ID = "0b44b37f-2299-47c8-bf5d-589995f8de96"


@pytest.fixture
def module(symphony_storage):
    module = SophosModule()
    module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": API_HOST,
        "client_id": "my-id",
        "client_secret": "my-password",
    }
    return module


@pytest.fixture
def mock_api(module):
    """Mock the OAuth2 token and whoami calls; the data region is DATA_REGION."""
    with requests_mock.Mocker() as mock:
        mock.post(
            module.configuration.oauth2_authorization_url,
            json={"access_token": "access_token", "token_type": "bearer", "expires_in": 3600},
        )
        mock.get(
            f"{API_HOST}/whoami/v1",
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {"global": "https://api.central.sophos.com", "dataRegion": DATA_REGION},
            },
        )
        yield mock
