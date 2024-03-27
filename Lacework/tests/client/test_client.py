import os
from datetime import datetime, timedelta

import pytest
import requests_mock
from requests.exceptions import HTTPError

from lacework_module.client import LaceworkApiClient
from lacework_module.client.auth import LaceworkAuthentication


def test_list_alerts():
    account = "example.lacework.net"
    key_id = "foo"
    secret = "bar"
    auth = LaceworkAuthentication(account, key_id, secret)
    client = LaceworkApiClient(account, auth=auth)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            url=f"https://{account}/api/v2/access/tokens",
            headers={"X-LW-UAKS": secret, "Content-Type": "application/json"},
            json={"token": "foo-token", "expiresAt": str(datetime.utcnow() + timedelta(seconds=3600))},
        )

        # flake8: noqa
        response = {
            "paging": {
                "rows": 1000,
                "totalRows": 3120,
                "urls": {"nextPage": "https://{account}/api/v2/Alerts/AbcdEfgh123..."},
            },
            "data": [
                {
                    "alertId": 855628,
                    "startTime": "2022-06-30T00:00:00.000Z",
                    "alertType": "MaliciousFile",
                    "severity": "Critical",
                    "internetExposure": "UnknownInternetExposure",
                    "reachability": "UnknownReachability",
                    "derivedFields": {"category": "Anomaly", "sub_category": "File", "source": "Agent"},
                    "endTime": "2022-06-30T01:00:00.000Z",
                    "lastUserUpdatedTime": "",
                    "status": "Open",
                    "alertName": "Clone of Cloud Activity log ingestion failure detected",
                    "alertInfo": {
                        "subject": "Clone of Cloud Activity log ingestion failure detected: `azure-al-india-dnd` (and `3` more) is failing for data ingestion into Lacework",
                        "description": "New integration failure detected for azure-al-india-dnd (and 3 more)",
                    },
                    "policyId": "CUSTOM_PLATFORM_130",
                },
                {
                    "alertId": 855629,
                    "startTime": "2022-06-30T00:00:00.000Z",
                    "alertType": "ChangedFile",
                    "severity": "Critical",
                    "internetExposure": "UnknownInternetExposure",
                    "reachability": "UnknownReachability",
                    "derivedFields": {"category": "Policy", "sub_category": "File", "source": "Agent"},
                    "endTime": "2022-06-30T01:00:00.000Z",
                    "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
                    "status": "Open",
                    "alertName": "Unauthorized API Call",
                    "alertInfo": {
                        "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                        "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework",
                    },
                },
            ],
        }
        # flake8: qa
        mock.get(f"https://{account}/api/v2/Alerts", json=response)
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
