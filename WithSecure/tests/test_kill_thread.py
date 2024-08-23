import pytest
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.constants import API_RESPONSE_ACTIONS_URL
from withsecure.kill_thread import ActionArguments, KillThread


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    action = KillThread(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {
        "client_id": "fusion_000000000000000000000000",
        "secret": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    return action


def test_kill_thread(action):
    response_payload = {"id": "b74a64f8-6545-4989-aeca-52a86c7c9e1e"}

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
            API_RESPONSE_ACTIONS_URL,
            status_code=207,
            json=response_payload,
        )

        response = action.run(
            arguments=ActionArguments(
                target="e297cbf5-ba53-4e66-909c-6d87527c4e98",
                organization_id="7301935a-6715-473b-a5af-9130e8c84821",
                thread_id=100,
            )
        )

        assert isinstance(response, dict)
        assert response == response_payload
