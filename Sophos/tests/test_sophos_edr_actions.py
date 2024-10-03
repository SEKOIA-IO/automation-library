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


def test_run_scan(module) -> None:
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"

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
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"

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

        url = f"{host}/endpoint/v1/endpoints/isolation"
        mock.post(
            url,
            json={
                "items": [
                    {
                        "id": "5cb82c71-035e-43af-a23c-760d5e7da94d",
                        "isolation": {
                            "enabled": True,
                            "lastEnabledAt": "2024-10-03 09.50.54 UTC",
                            "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
                            "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
                        },
                    }
                ]
            },
        )
        isolate_action = ActionSophosEDRIsolateEndpoint(module)
        isolate_action.run({"endpoints_ids": ["0b44b37f-2299-47c8-bf5d-589995f8de96"]})


def test_deisolate_endpoint(module):
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"

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

        url = f"{host}/endpoint/v1/endpoints/isolation"
        mock.post(
            url,
            json={
                "items": [
                    {
                        "id": "5cb82c71-035e-43af-a23c-760d5e7da94d",
                        "isolation": {
                            "enabled": False,
                            "lastEnabledAt": "2024-10-03 09.50.54 UTC",
                            "lastEnabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
                            "lastDisabledBy": {"id": "a1fac7fe-1cf3-46c8-9b8c-9976f518f726"},
                        },
                    }
                ]
            },
        )
        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module)
        deisolate_action.run({"endpoints_ids": ["0b44b37f-2299-47c8-bf5d-589995f8de96"]})


def test_error(module):
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"

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

        url = f"{host}/endpoint/v1/endpoints/isolation"
        mock.post(
            url,
            status_code=400,
            json={
                "error": "badRequest",
                "correlationId": "c5bd922b-febb-45e2-a9f1-02fb2a8f88d9",
                "requestId": "16e35810-0be1-430b-9978-d1e8f959a422",
                "createdAt": "2024-10-02T13:52:36.194125443Z",
                "message": "Invalid request",
            },
        )
        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module)

        with pytest.raises(requests.exceptions.HTTPError):
            deisolate_action.run({"endpoints_ids": ["0b44b37f-2299-47c8-bf5d-589995f8de96"]})
