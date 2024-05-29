import os
from datetime import datetime, timedelta
from typing import Any

import pytest
import requests_mock
from faker import Faker

from lacework_module.client import LaceworkApiClient
from lacework_module.client.auth import LaceworkAuthentication


def test_list_alerts(session_faker: Faker, alerts_response: dict[str, Any]):
    account = session_faker.word()
    key_id = session_faker.word()
    secret = session_faker.word()
    auth = LaceworkAuthentication(account, key_id, secret)
    client = LaceworkApiClient(account, auth=auth)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            url="https://{account}/api/v2/access/tokens".format(account=account),
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={"token": "foo-token", "expiresAt": str(datetime.utcnow() + timedelta(seconds=3600))},
        )

        mock.get(f"https://{account}/api/v2/Alerts", json=alerts_response)
        list_events_response = client.list_alerts()

        assert list_events_response is not None


@pytest.mark.skipif("{'LACEWORK_ID', 'LACEWORK_SECRET'}.issubset(os.environ.keys()) == False")
def test_authentication_integration(symphony_storage):
    account = os.environ["LACEWORK_URL"]
    key_id = os.environ["LACEWORK_ACCESS_KEY"]
    secret = os.environ["LACEWORK_SECRET_KEY"]
    auth = LaceworkAuthentication(account, key_id, secret)
    client = LaceworkApiClient(account, auth=auth)

    response = client.list_alerts()
    assert response.status_code < 300
