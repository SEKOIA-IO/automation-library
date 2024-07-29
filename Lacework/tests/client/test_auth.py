import os
from datetime import datetime, timedelta, timezone

import pytest
import requests_mock
from faker import Faker

from lacework_module.client.auth import LaceworkAuthentication


def test_get_credentials(session_faker: Faker):
    account = session_faker.word()
    key_id = session_faker.word()
    secret = session_faker.word()
    auth = LaceworkAuthentication(account, key_id, secret)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            url="https://{account}/api/v2/access/tokens".format(account=account),
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={
                "token": "foo-token",
                "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=3600)).isoformat(),
            },
        )

        current_dt = datetime.now(timezone.utc)
        credentials = auth.get_credentials()
        assert credentials.token == "foo-token"
        assert credentials.expiresAt > current_dt + timedelta(seconds=3550)
        assert credentials.expiresAt < current_dt + timedelta(seconds=3650)
        assert credentials.authorization == "Bearer foo-token"


def test_get_credentials_request_new_token_only_when_needed(session_faker: Faker):
    account = session_faker.word()
    key_id = session_faker.word()
    secret = session_faker.word()
    auth = LaceworkAuthentication(account, key_id, secret)

    with requests_mock.Mocker() as mock:
        p1 = mock.post(
            url="https://{account}/api/v2/access/tokens".format(account=account),
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={"token": "123456", "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=3600)).isoformat()},
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 123456"

        p2 = mock.post(
            url=f"https://{account}/api/v2/access/tokens",
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={"token": "78910", "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=10000)).isoformat()},
        )
        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        p3 = mock.post(
            url="https://{account}/api/v2/access/tokens".format(account=account),
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={"token": "78910", "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=10000)).isoformat()},
        )

        credentials = auth.get_credentials()
        assert credentials.authorization == "Bearer 78910"

        assert p1.called
        assert p2.called
        assert not p3.called


@pytest.mark.skipif("{'LACEWORK_ID', 'LACEWORK_SECRET'}.issubset(os.environ.keys()) == False")
def test_authentication_integration(symphony_storage):
    account = os.environ["LACEWORK_URL"]
    key_id = os.environ["LACEWORK_ACCESS_KEY"]
    secret = os.environ["LACEWORK_SECRET_KEY"]
    auth = LaceworkAuthentication(account, key_id, secret)

    credentials = auth.get_credentials()
    assert credentials.token is not None
    assert credentials.expiresAt is not None
