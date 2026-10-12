import pytest
import requests.exceptions
import requests_mock
from unittest.mock import Mock
from pydantic import ValidationError

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


@pytest.mark.parametrize(
    "action_class", [ActionSophosEDRScan, ActionSophosEDRIsolateEndpoint, ActionSophosEDRDeIsolateEndpoint]
)
@pytest.mark.parametrize("arguments", [{}, {"endpoint_id": ""}, {"endpoint_id": "   "}, {"endpoint_id": "not-a-uuid"}])
def test_actions_require_valid_endpoint_id(module, action_class, arguments) -> None:
    action = action_class(module)
    action.call_endpoint = Mock()

    with pytest.raises(ValidationError):
        action.run(arguments)

    action.call_endpoint.assert_not_called()


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


def test_isolate_endpoint_sends_comment_and_returns_api_response(module):
    endpoint_id = "0b44b37f-2299-47c8-bf5d-589995f8de96"
    current_status = {"enabled": False}
    updated_status = {"enabled": True, "lastEnabledAt": "2024-10-03 09.50.54 UTC"}

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/{endpoint_id}/isolation"
        mock.get(url, json=current_status)
        patch_mock = mock.patch(url, json=updated_status)

        isolate_action = ActionSophosEDRIsolateEndpoint(module)
        result = isolate_action.run({"endpoint_id": endpoint_id, "comment": "Suspicious activity"})

    assert result == updated_status
    assert patch_mock.call_count == 1
    assert patch_mock.last_request.json() == {"enabled": True, "comment": "Suspicious activity"}


def test_isolate_endpoint_already_isolated_skips_update(module):
    endpoint_id = "0b44b37f-2299-47c8-bf5d-589995f8de96"

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/{endpoint_id}/isolation"
        mock.get(url, json={"enabled": True})
        patch_mock = mock.patch(url, json={})

        result = ActionSophosEDRIsolateEndpoint(module).run({"endpoint_id": endpoint_id})

    assert result == {"enabled": True, "message": "Already enabled"}
    assert patch_mock.call_count == 0


def test_isolation_change_rejected_too_soon_is_reported(module):
    endpoint_id = "0b44b37f-2299-47c8-bf5d-589995f8de96"

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/{endpoint_id}/isolation"
        mock.get(url, json={"enabled": True})
        mock.patch(url, json={"error": "badRequest", "requestId": "16e35810"}, status_code=400)

        result = ActionSophosEDRDeIsolateEndpoint(module).run({"endpoint_id": endpoint_id})

    assert result == {
        "error": "Isolation status was changed recently",
        "message": "We recommend that you wait for a period of time between turning endpoint isolation on and off",
        "requestId": "16e35810",
        "enabled": True,
    }


def test_call_endpoint_raises_on_http_error(module):
    endpoint_id = "0b44b37f-2299-47c8-bf5d-589995f8de96"

    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)
        mock.post(
            f"{host}/endpoint/v1/endpoints/{endpoint_id}/scans",
            status_code=403,
            json={"error": "forbidden", "message": "Access denied", "correlationId": "c5bd922b"},
        )

        with pytest.raises(requests.exceptions.HTTPError):
            ActionSophosEDRScan(module).run({"endpoint_id": endpoint_id})
