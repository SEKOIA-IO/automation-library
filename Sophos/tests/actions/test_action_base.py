import pytest
import requests
import requests_mock

from sophos_module.actions.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint


def test_error(module, add_auth_mock):
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

        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module, add_auth_mock)
        deisolate_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})


@pytest.mark.parametrize("method", ["get", "post", "patch"])
def test_call_endpoint_methods(module, add_auth_mock, method):
    with requests_mock.Mocker() as mock:
        add_auth_mock(mock, "https://api-eu01.central.sophos.com", module)
        getattr(mock, method)("https://api-eu.central.sophos.com/endpoint/v1/settings", json={"ok": True})

        action = ActionSophosEDRDeIsolateEndpoint(module)
        assert action.call_endpoint(method.upper(), "endpoint/v1/settings", data={"a": 1}) == {"ok": True}
        assert mock.last_request.method == method.upper()


def test_call_endpoint_region_url(module, add_auth_mock):
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)
        mock.get(f"{host}/endpoint/v1/endpoints", json={"items": []})

        action = ActionSophosEDRDeIsolateEndpoint(module)
        assert action.region_base_url == host
        assert action.call_endpoint("get", "endpoint/v1/endpoints", use_region_url=True) == {"items": []}


def test_call_endpoint_error(module, add_auth_mock):
    with requests_mock.Mocker() as mock:
        add_auth_mock(mock, "https://api-eu01.central.sophos.com", module)
        mock.post(
            "https://api-eu.central.sophos.com/endpoint/v1/settings",
            status_code=400,
            json={"error": "badRequest", "message": "Invalid request"},
        )

        action = ActionSophosEDRDeIsolateEndpoint(module)
        with pytest.raises(requests.HTTPError):
            action.call_endpoint("post", "endpoint/v1/settings")


def test_call_endpoint_unsupported_method(module):
    with pytest.raises(AssertionError):
        ActionSophosEDRDeIsolateEndpoint(module).call_endpoint("delete", "endpoint/v1/settings")
