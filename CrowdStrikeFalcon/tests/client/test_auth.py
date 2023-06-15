from datetime import datetime, timedelta

import requests_mock

from crowdstrike_falcon.client.auth import CrowdStrikeFalconApiAuthentication


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
