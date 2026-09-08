import pytest
import requests_mock
from pydantic import ValidationError

from microsoft_outlook_modules.action_update_message import UpdateMessageAction


def test_update_message(configured_action, message_2):
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
        result = action.run(arguments={"user": "1111", "message_id": "2222", "subject": "Changed Subject"})
        assert result["message_id"] == message_2["id"]
        assert result["internet_message_id"] == message_2["internetMessageId"]
        assert result["received_date_time"] == message_2["receivedDateTime"]
        assert result["to_recipients"][0]["email_address"]["address"] == "recipient@example.com"


def test_update_message_falls_back_to_message_id_for_non_dict_payload(configured_action):
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
            json=["message"],
        )

        action = configured_action(UpdateMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222", "subject": "Changed Subject"})
        assert result == {"message_id": "2222"}


def test_update_message_falls_back_to_message_id_for_non_json_payload(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "PATCH",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222",
            status_code=204,
            content=b"",
        )

        action = configured_action(UpdateMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222", "subject": "Changed Subject"})
        assert result == {"message_id": "2222"}


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
