import pytest
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.constants import API_DEVICES_OPERATION_URL
from withsecure.isolate_device_from_network_action import ActionArguments, IsolateDeviceFromNetworkAction


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    action = IsolateDeviceFromNetworkAction(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {
        "client_id": "fusion_000000000000000000000000",
        "secret": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    return action


def test_run_to_isolate_a_computer_with_message(action):
    response_payload = {
        "multistatus": [
            {"target": "e297cbf5-ba53-4e66-909c-6d87527c4e98", "status": 202, "operationId": "1766423938040964633"}
        ],
        "transactionId": "0000-981c1d1730764143",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            API_AUTHENTICATION_URL,
            status_code=200,
            json={
                "access_token": "eHcMH7mMmrVK2vaTMnqwRk8ono4yVeBMO6/x2L887as",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )
        mock_requests.post(
            API_DEVICES_OPERATION_URL,
            status_code=207,
            json=response_payload,
        )

        response = action.run(
            arguments=ActionArguments(
                target="e297cbf5-ba53-4e66-909c-6d87527c4e98", message="Example of a test message"
            )
        )

        assert isinstance(response, dict)
        assert response_payload == response
