from datetime import datetime, timedelta

import pytest
import requests_mock

from crowdstrike_falcon.client.auth import CrowdStrikeFalconApiAuthentication, AuthenticationError


def test_get_credentials():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    auth = CrowdStrikeFalconApiAuthentication(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        current_dt = datetime.utcnow()
        credentials = auth.get_credentials()
        assert credentials.token_type == "bearer"
        assert credentials.access_token == "foo-token"
        assert credentials.expires_at > (current_dt + timedelta(seconds=1750))
        assert credentials.expires_at < (current_dt + timedelta(seconds=1850))
        assert credentials.authorization == "Bearer foo-token"


def test_get_credentials_unauthorized():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    auth = CrowdStrikeFalconApiAuthentication(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            status_code=401,
            json={
                "meta": {
                    "trace_id": "00000000-0000-0000-0000-000000000000",
                },
                "errors": [
                    {
                        "code": 401,
                        "message": "Unauthorized: Please provide trace-id='00000000-0000-0000-0000-000000000000' to support",
                    }
                ],
            },
        )

        with pytest.raises(
            AuthenticationError,
            match="Unauthorized: Please provide trace-id='00000000-0000-0000-0000-000000000000' to support",
        ):
            auth.get_credentials()


def test_get_credentials_forbidden():
    base_url = "https://my.fake.sekoia"
    client_id = "foo"
    client_secret = "bar"
    auth = CrowdStrikeFalconApiAuthentication(base_url, client_id, client_secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            f"{base_url}/oauth2/token",
            status_code=403,
            json={
                "meta": {
                    "trace_id": "00000000-0000-0000-0000-000000000000",
                },
                "errors": [
                    {
                        "code": 403,
                        "message": "Failed to issue access token - Client authentication failed (e.g., unknown client, no client authentication included, or unsupported authentication method)",
                    }
                ],
            },
        )

        with pytest.raises(
            AuthenticationError,
            match="Forbidden: Failed to issue access token - Client authentication failed \(e.g., unknown client, no client authentication included, or unsupported authentication method\)",
        ):
            auth.get_credentials()
