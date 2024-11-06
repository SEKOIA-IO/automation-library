import pytest
import requests.exceptions
import requests_mock

from sophos_module.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint
from sophos_module.action_sophos_edr_isolate import ActionSophosEDRIsolateEndpoint
from sophos_module.action_sophos_edr_run_scan import ActionSophosEDRScan
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


def add_auth_mock(mock, host, module):
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


def test_run_scan(module) -> None:
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/0b44b37f-2299-47c8-bf5d-589995f8de96/scans"
        mock.post(
            url,
            json={
                "id": "41d45256-d5e0-4f56-bfb4-57c5de6909d9",
                "status": "requested",
                "requestedAt": "2024-10-03T10:29:58.170278201Z",
            },
        )
        scan_action = ActionSophosEDRScan(module)
        scan_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})


def test_isolate_endpoint(module):
    message = {
        "enabled": True,
        "lastEnabledAt": "2024-10-03 09.50.54 UTC",
        "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
        "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
    }

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/0b44b37f-2299-47c8-bf5d-589995f8de96/isolation"
        mock.get(
            url,
            json=message,
        )
        mock.patch(
            url,
            json=message,
        )
        isolate_action = ActionSophosEDRIsolateEndpoint(module)
        isolate_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})


def test_deisolate_endpoint(module):
    message = {
        "enabled": False,
        "lastEnabledAt": "2024-10-03 09.50.54 UTC",
        "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
        "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
    }

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/0b44b37f-2299-47c8-bf5d-589995f8de96/isolation"
        mock.get(
            url,
            json=message,
        )
        mock.patch(
            url,
            json=message,
        )

        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module)
        deisolate_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})


def test_error(module):
    message_1 = {
        "enabled": True,
        "lastEnabledAt": "2024-10-03 09.50.54 UTC",
        "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
        "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
    }
    message_2 = {
        "error": "badRequest",
        "correlationId": "c5bd922b-febb-45e2-a9f1-02fb2a8f88d9",
        "requestId": "16e35810-0be1-430b-9978-d1e8f959a422",
        "createdAt": "2024-10-03T13:52:36.194125443Z",
        "message": "Invalid request",
    }
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/0b44b37f-2299-47c8-bf5d-589995f8de96/isolation"
        mock.get(
            url,
            json=message_1,
        )
        mock.patch(url, json=message_2, status_code=400)

        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module)
        deisolate_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})
