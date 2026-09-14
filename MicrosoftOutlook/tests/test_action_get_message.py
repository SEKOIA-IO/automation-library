import pytest
import requests_mock
from requests import HTTPError

from microsoft_outlook_modules.action_base import GraphAPIException
from microsoft_outlook_modules.action_get_message import GetMessageAction


def test_get_message(configured_action, get_message_1):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("GET", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", json=get_message_1)

        action = configured_action(GetMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222"})
        assert result["message_id"] == get_message_1["id"]
        assert result["internet_message_id"] == get_message_1["internetMessageId"]
        assert result["received_date_time"] == get_message_1["receivedDateTime"]
        assert result["to_recipients"][0]["email_address"]["address"] == "recipient@example.com"


def test_get_message_keeps_non_dict_payload_unchanged(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("GET", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", json=["message"])

        action = configured_action(GetMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222"})
        assert result == ["message"]


def test_get_message_message_id_falls_back_to_input_message_id(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222",
            json={"id": None, "subject": "test"},
        )

        action = configured_action(GetMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222"})
        assert result["message_id"] == "2222"


@pytest.mark.parametrize(
    "status_code,body,expected_exception",
    [
        (400, '{"error":{"code":"ErrorInvalidIdMalformed","message":"Id is malformed."}}', GraphAPIException),
        (500, "server_error", HTTPError),
    ],
)
def test_get_message_error_handling(configured_action, status_code, body, expected_exception):
    class FakeResponse:
        def __init__(self, response_status_code: int, response_text: str):
            self.ok = False
            self.status_code = response_status_code
            self.text = response_text
            self.reason = "Bad Request" if response_status_code == 400 else "Internal Server Error"

        def raise_for_status(self):
            raise HTTPError(f"{self.status_code} {self.reason}")

    action = configured_action(GetMessageAction)
    action.log = lambda **_kwargs: None
    with pytest.raises(expected_exception):
        action.handle_response(FakeResponse(status_code, body))
