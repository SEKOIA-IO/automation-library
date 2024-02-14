import os
from datetime import datetime, timedelta

import pytest
import requests_mock

from lacework_module.client.auth import LaceworkAuthentication


def test_get_credentials():
    lacework_url="api"
    access_key="foo"
    secret_key="bar"
    auth = LaceworkAuthentication(lacework_url, access_key, secret_key)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            url=f"https://{lacework_url}.lacework.net/api/v2/access/tokens",
            headers={
                    "X-LW-UAKS": secret_key,
                    "Content-Type": "application/json"
                },
            json={
                    "keyId": access_key,
                    "expiryTime": 3600
                }
        )

        current_dt = datetime.utcnow()
        credentials = auth.get_credentials()
        assert credentials.token == "foo-token"
        assert credentials.expiresAt == current_dt + timedelta(seconds=3600)
        assert credentials.authorization == "Bearer foo-token"


def test_get_credentials_request_new_token_only_when_needed():
    lacework_url="api"
    access_key="foo"
    secret_key="bar"
    auth = LaceworkAuthentication(lacework_url, access_key, secret_key)

    with requests_mock.Mocker() as mock:
        p1 = mock.post(
            url=f"https://{lacework_url}.lacework.net/api/v2/access/tokens",
            headers={
                    "X-LW-UAKS": secret_key,
                    "Content-Type": "application/json"
                },
            json={
                    "keyId": access_key,
                    "expiryTime": 10
                }
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 123456"

        p2 = mock.post(
            url=f"https://{lacework_url}.lacework.net/api/v2/access/tokens",
            headers={
                    "X-LW-UAKS": secret_key,
                    "Content-Type": "application/json"
                },
            json={
                    "keyId": access_key,
                    "expiryTime": 3600
                }
        )
        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        p3 = mock.post(
            url=f"https://{lacework_url}.lacework.net/api/v2/access/tokens",
            headers={
                    "X-LW-UAKS": secret_key,
                    "Content-Type": "application/json"
                },
            json={
                    "keyId": access_key,
                    "expiryTime": 3600
                }
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        assert p1.called
        assert p2.called
        assert not p3.called


@pytest.mark.skipif("{'LACEWORK_ID', 'LACEWORK_SECRET'}.issubset(os.environ.keys()) == False")
def test_authentication_integration(symphony_storage):
    lacework_url=os.environ["LACEWORK_URL"]
    access_key= os.environ["LACEWORK_ACCESS_KEY"]
    secret_key=os.environ["LACEWORK_SECRET_KEY"]
    auth = LaceworkAuthentication(lacework_url, access_key, secret_key)

    credentials = auth.get_credentials()
    assert credentials.token is not None
    assert credentials.expiresAt is not None