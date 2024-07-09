import os
import time

import pytest
import requests_mock

from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication


def test_list_siem_events():
    api_host_url = "https://api-eu.central.sophos.com"
    authorization_url = "https://id.sophos.com/api/v2/oauth2/token"
    client_id = "foo"
    client_secret = "bar"
    auth = SophosApiAuthentication(api_host_url, authorization_url, client_id, client_secret)
    client = SophosApiClient(auth=auth)

    data_region_url = "https://api-eu02.central.sophos.com"
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
                "apiHosts": {"global": "https://api.central.sophos.com", "dataRegion": data_region_url},
            },
        )

        # flake8: noqa
        response = {
            "has_more": False,
            "next_cursor": "VjJfQ1VSU09SfDIwMTktMDQtMDFUMTg6MjU6NDEuNjA2Wg==",
            "items": [
                {
                    "when": "2019-04-01T15:11:09.759Z",
                    "id": "cbaff14f-a36b-46bd-8e83-6017ad79cdef",
                    "customer_id": "816f36ee-dd2e-4ccd-bb12-cea766c28ade",
                    "severity": "low",
                    "created_at": "2019-04-01T15:11:09.984Z",
                    "source_info": {"ip": "10.1.39.32"},
                    "endpoint_type": "server",
                    "endpoint_id": "c80c2a87-42f2-49b2-bab7-5031b69cd83e",
                    "origin": None,
                    "type": "Event::Endpoint::Registered",
                    "location": "mock_Mercury_1",
                    "source": "n/a",
                    "group": "PROTECTION",
                    "name": "New server registered: mock_Mercury_1",
                },
                {
                    "when": "2019-04-01T15:11:41.000Z",
                    "id": "5bc48f19-3905-4f72-9f79-cd381c8e92ce",
                    "customer_id": "816f36ee-dd2e-4ccd-bb12-cea766c28ade",
                    "severity": "medium",
                    "created_at": "2019-04-01T15:11:41.053Z",
                    "source_info": {"ip": "10.1.39.32"},
                    "endpoint_type": "server",
                    "endpoint_id": "c80c2a87-42f2-49b2-bab7-5031b69cd83e",
                    "origin": None,
                    "type": "Event::Endpoint::Threat::Detected",
                    "location": "mock_Mercury_1",
                    "source": "n/a",
                    "group": "MALWARE",
                    "name": "Malware detected: 'Eicar-AV-Test' at 'C:\\Program Files (x86)\\Trojan Horse\\bin\\eicar.com'",
                },
            ],
        }
        # flake8: qa
        mock.get(f"{data_region_url}/siem/v1/events", json=response)
        list_events_response = client.list_siem_events()
        assert list_events_response is not None


@pytest.mark.skipif("{'SOPHOS_CLIENT_ID', 'SOPHOS_CLIENT_SECRET'}.issubset(os.environ.keys()) == False")
def test_authentication_integration(symphony_storage):
    api_host_url = os.environ.get("SOPHOS_URL", "https://api-eu.central.sophos.com")
    authorization_url = os.environ.get("SOPHOS_AUTH_URL", "https://id.sophos.com/api/v2/oauth2/token")
    client_id = os.environ["SOPHOS_CLIENT_ID"]
    client_secret = os.environ["SOPHOS_CLIENT_SECRET"]
    auth = SophosApiAuthentication(api_host_url, authorization_url, client_id, client_secret)
    client = SophosApiClient(auth=auth)

    response = client.list_siem_events(parameters={"from_date": int(time.time()) - 300})
    assert response.status_code < 300
