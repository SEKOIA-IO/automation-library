import pytest
import requests_mock

from microsoft_outlook_modules.action_delete_message import DeleteMessageAction


@pytest.mark.parametrize(
    "message_id_input",
    [
        "2222",
        {"message_id": "2222"},
    ],
    ids=["string_message_id", "foreach_message_object"],
)
def test_delete_message(configured_action, message_id_input):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock.register_uri(
            "DELETE",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222",
            status_code=204,
            content=b"",
        )

        action = configured_action(DeleteMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": message_id_input})
        assert result == {
            "status": "deleted",
            "action": "delete_a_message",
            "target_message_id": "2222",
            "user": "1111",
        }


@pytest.mark.parametrize("invalid_message_id", [{"subject": "test"}, 123])
def test_delete_message_rejects_invalid_message_id_values(configured_action, invalid_message_id):
    _ = configured_action(DeleteMessageAction)
    with pytest.raises(ValueError, match="message_id must be a string or a message object"):
        DeleteMessageAction._resolve_message_id(invalid_message_id)  # type: ignore[arg-type]
