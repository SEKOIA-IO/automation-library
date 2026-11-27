import requests_mock

from sophos_module.actions.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint


def test_deisolate_endpoint(module, add_auth_mock):
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

        deisolate_action = ActionSophosEDRDeIsolateEndpoint(module, add_auth_mock)
        deisolate_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})
