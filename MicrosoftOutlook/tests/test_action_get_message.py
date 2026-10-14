import pytest
import requests_mock
from requests import HTTPError

from microsoft_outlook_modules.action_base import GraphAPIException
from microsoft_outlook_modules.action_get_message import GetMessageAction


@pytest.mark.parametrize(
    "message_id_input",
    [
        "2222",
        {"message_id": "2222"},
    ],
    ids=["string_message_id", "foreach_message_object"],
)
def test_get_message(configured_action, get_message_1, message_id_input):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("GET", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", json=get_message_1)

        action = configured_action(GetMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": message_id_input})
        assert result["user"] == "1111"
        assert result["message_id"] == get_message_1["id"]
        assert result["internet_message_id"] == get_message_1["internetMessageId"]
        assert result["received_date_time"] == get_message_1["receivedDateTime"]
        assert result["to_recipients"][0]["email_address"]["address"] == "recipient@example.com"


@pytest.mark.parametrize("invalid_message_id", [{"subject": "test"}, 123])
def test_get_message_rejects_invalid_message_id_values(configured_action, invalid_message_id):
    _ = configured_action(GetMessageAction)
    with pytest.raises(ValueError, match="message_id must be a string or a message object"):
        GetMessageAction._resolve_message_id(invalid_message_id)  # type: ignore[arg-type]


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
        assert result["user"] == "1111"


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
