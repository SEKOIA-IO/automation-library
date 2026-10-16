import pytest
import requests_mock

from microsoft_outlook_modules.action_forward_message import ForwardMessageAction


@pytest.mark.parametrize(
    "message_id_input",
    [
        "2222",
        {"message_id": "2222"},
    ],
    ids=["string_message_id", "foreach_message_object"],
)
def test_forward_message(configured_action, message_id_input):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222/forward",
            status_code=202,
            content=b"",
        )

        action = configured_action(ForwardMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "message_id": message_id_input,
                "recipients": ["john.doe@example.com"],
            }
        )
        assert result == {
            "action": "forward_message",
            "comment": "",
            "recipients": ["john.doe@example.com"],
            "status": "forwarded",
            "target_message_id": "2222",
            "user": "1111",
        }


@pytest.mark.parametrize("invalid_message_id", [{"subject": "x"}, 123])
def test_forward_message_rejects_invalid_message_id_values(configured_action, invalid_message_id):
    _ = configured_action(ForwardMessageAction)
    with pytest.raises(ValueError, match="message_id must be a string or a message object"):
        ForwardMessageAction._resolve_message_id(invalid_message_id)  # type: ignore[arg-type]
