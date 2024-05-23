import pytest
import requests_mock

from withsecure import WithSecureModule
from withsecure.client.auth import API_AUTHENTICATION_URL
from withsecure.comment_incident import ActionArguments, CommentIncident
from withsecure.constants import API_COMMENT_INCIDENT_URL


@pytest.fixture
def action(data_storage):
    def fake_log_cb(message: str, level: str):
        print(message)
        return None

    module = WithSecureModule()
    action = CommentIncident(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    action.log = fake_log_cb
    action.module.configuration = {
        "client_id": "fusion_000000000000000000000000",
        "secret": "0000000000000000000000000000000000000000000000000000000000000000",
    }
    return action


def test_run_to_comment_an_incident(action):
    response_payload = {
        "items": [
            {"incidentId": "2c902c73-e2a6-40fd-9532-257ee102e1c1", "comment": "example comment"},
            {"incidentId": "cc8b996f-1d50-40cc-a942-686f82fcd3fc", "comment": "example comment"},
        ]
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
            API_COMMENT_INCIDENT_URL,
            status_code=207,
            json=response_payload,
        )

        response = action.run(
            arguments=ActionArguments(
                target="2c902c73-e2a6-40fd-9532-257ee102e1c1", comment="Example of a incident comment"
            )
        )

        assert isinstance(response, dict)
        assert response_payload == response
