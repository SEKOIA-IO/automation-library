import pytest
import requests_mock
from pydantic import ValidationError

from microsoft_outlook_modules.action_update_message import UpdateMessageAction


@pytest.mark.parametrize(
    "message_id_input",
    [
        "2222",
        {"message_id": "2222"},
    ],
    ids=["string_message_id", "foreach_message_object"],
)
def test_update_message(configured_action, message_2, message_id_input):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "PATCH", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", status_code=200, json=message_2
        )

        action = configured_action(UpdateMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": message_id_input, "subject": "Changed Subject"})
        assert result["user"] == "1111"
        assert result["action"] == "update_message"
        assert result["status"] == "updated"
        assert result["updated_subject"] == "Changed Subject"
        assert result["recipients"] is None
        assert result["sender"]["email_address"]["address"] == "sender@example.com"
        assert result["updated_sender"] is None
        assert result["message_id"] == message_2["id"]
        assert result["internet_message_id"] == message_2["internetMessageId"]
        assert result["received_date_time"] == message_2["receivedDateTime"]
        assert result["to_recipients"][0]["email_address"]["address"] == "recipient@example.com"


@pytest.mark.parametrize("invalid_message_id", [{"subject": "x"}, 123])
def test_update_message_rejects_invalid_message_id_values(configured_action, invalid_message_id):
    _ = configured_action(UpdateMessageAction)
    with pytest.raises(ValueError, match="message_id must be a string or a message object"):
        UpdateMessageAction._resolve_message_id(invalid_message_id)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "status_code,response_payload",
    [
        (200, {"json": ["message"]}),
        (204, {"content": b""}),
    ],
)
def test_update_message_falls_back_to_message_id_for_non_standard_payload(
    configured_action, status_code, response_payload
):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "PATCH",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222",
            status_code=status_code,
            **response_payload,
        )

        action = configured_action(UpdateMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222", "subject": "Changed Subject"})
        assert result == {
            "action": "update_message",
            "bcc": None,
            "cc": None,
            "from": None,
            "importance": None,
            "message_id": "2222",
            "recipients": None,
            "sender": None,
            "status": "updated",
            "updated_from": None,
            "updated_sender": None,
            "updated_subject": "Changed Subject",
            "user": "1111",
        }


def test_update_message_with_all_optional_fields(configured_action, message_2):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "PATCH",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222",
            status_code=200,
            json=message_2,
        )

        action = configured_action(UpdateMessageAction)
        action.run(
            arguments={
                "user": "1111",
                "message_id": "2222",
                "content": "Updated content",
                "recipients": ["recipient@example.com"],
                "bcc": ["bcc@example.com"],
                "cc": ["cc@example.com"],
                "sender": "sender@example.com",
                "from": "owner@example.com",
                "subject": "Updated subject",
                "importance": "Normal",
            }
        )

        request = mock.request_history[1]
        payload = request.json()
        assert payload["body"]["content"] == "Updated content"
        assert payload["toRecipients"][0]["emailAddress"]["address"] == "recipient@example.com"
        assert payload["bccRecipients"][0]["emailAddress"]["address"] == "bcc@example.com"
        assert payload["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
        assert payload["sender"]["emailAddress"]["address"] == "sender@example.com"
        assert payload["from"]["emailAddress"]["address"] == "owner@example.com"


def test_update_message_requires_at_least_one_update_field(configured_action):
    action = configured_action(UpdateMessageAction)

    with pytest.raises(ValidationError, match="At least one updatable field must be provided"):
        action.run(arguments={"user": "1111", "message_id": "2222"})
