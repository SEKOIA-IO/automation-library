import os
from datetime import datetime, timedelta

import pytest
import requests_mock

from sophos_module.client.auth import SophosApiAuthentication


def test_get_credentials():
    api_host_url = "https://api-eu.central.sophos.com"
    authorization_url = "https://id.sophos.com/api/v2/oauth2/token"
    client_id = "foo"
    client_secret = "bar"
    auth = SophosApiAuthentication(api_host_url, authorization_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            authorization_url,
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "scope": "our-scope",
                "expires_in": 1799,
            },
        )

        mock.get(
            f"{api_host_url}/whoami/v1",
            status_code=200,
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {
                    "global": "https://api.central.sophos.com",
                    "dataRegion": "https://api-eu02.central.sophos.com",
                },
            },
        )

        current_dt = datetime.utcnow()
        credentials = auth.get_credentials()
        assert credentials.token_type == "bearer"
        assert credentials.access_token == "foo-token"
        assert credentials.expires_at > (current_dt + timedelta(seconds=1750))
        assert credentials.expires_at < (current_dt + timedelta(seconds=1850))
        assert credentials.authorization == "Bearer foo-token"
        assert credentials.tenancy_type == "tenant"
        assert credentials.tenancy_id == "ea106f70-96b1-4851-bd31-e4395ea407d2"
        assert credentials.tenancy_header == {"X-Tenant-ID": "ea106f70-96b1-4851-bd31-e4395ea407d2"}


def test_get_credentials_request_new_token_only_when_needed():
    api_host_url = "https://api-eu.central.sophos.com"
    authorization_url = "https://id.sophos.com/api/v2/oauth2/token"
    client_id = "foo"
    client_secret = "bar"
    auth = SophosApiAuthentication(api_host_url, authorization_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        p1 = mock.post(
            authorization_url,
            json={
                "access_token": "123456",
                "expires_in": 10,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        mock.get(
            f"{api_host_url}/whoami/v1",
            status_code=200,
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {
                    "global": "https://api.central.sophos.com",
                    "dataRegion": "https://api-eu02.central.sophos.com",
                },
            },
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 123456"

        p2 = mock.post(
            authorization_url,
            json={
                "access_token": "78910",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )
        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        p3 = mock.post(
            authorization_url,
            json={
                "access_token": "11111",
                "expires_in": 10000,
                "scope": "our-scope",
                "token_type": "bearer",
            },
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        assert p1.called
        assert p2.called
        assert not p3.called


@pytest.mark.skipif("{'SOPHOS_CLIENT_ID', 'SOPHOS_CLIENT_SECRET'}.issubset(os.environ.keys()) == False")
def test_authentication_integration(symphony_storage):
    api_host_url = os.environ.get("SOPHOS_URL", "https://api-eu.central.sophos.com")
    authorization_url = os.environ.get("SOPHOS_AUTH_URL", "https://id.sophos.com/api/v2/oauth2/token")
    client_id = os.environ["SOPHOS_CLIENT_ID"]
    client_secret = os.environ["SOPHOS_CLIENT_SECRET"]
    auth = SophosApiAuthentication(api_host_url, authorization_url, client_id, client_secret)

    credentials = auth.get_credentials()
    assert credentials.token_type is not None
    assert credentials.access_token is not None
    assert credentials.expires_at is not None
    assert credentials.tenancy_type is not None
    assert credentials.tenancy_id is not None
