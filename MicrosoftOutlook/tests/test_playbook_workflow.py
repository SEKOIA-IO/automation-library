import pytest
import requests_mock

from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction


@pytest.mark.parametrize(
    "message_identifier",
    [
        {"email_message_id": "<malicious-message-id@example.com>"},
        {"email_local_id": "00000000-0000-4000-8000-000000000123"},
    ],
)
def test_playbook_workflow_detect_confirm_resolve_delete(configured_action, message_identifier):
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
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={
                "value": [
                    {
                        "id": "graph-item-id-1",
                        "internetMessageId": "<malicious-message-id@example.com>",
                        "subject": "Urgent security verification required",
                        "receivedDateTime": "2026-08-10T09:20:25Z",
                    }
                ]
            },
        )

        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages/graph-item-id-1",
            json={
                "id": "graph-item-id-1",
                "internetMessageId": "<malicious-message-id@example.com>",
                "subject": "Urgent security verification required",
                "bodyPreview": "Click immediately to avoid suspension",
            },
        )

        mock.register_uri(
            "DELETE",
            "https://graph.microsoft.com/v1.0/users/1111/messages/graph-item-id-1",
            status_code=204,
            content=b"",
        )

        search_action = configured_action(SearchMessagesAction)
        search_result = search_action.run(arguments={"user": "1111", **message_identifier})
        assert len(search_result["messages"]) == 1
        assert "urgent" in search_result["messages"][0]["subject"].lower()

        resolve_action = configured_action(ResolveMessageAction)
        resolve_result = resolve_action.run(arguments={"user": "1111", **message_identifier})
        message_id = resolve_result["message_id"]
        assert message_id == "graph-item-id-1"

        get_action = configured_action(GetMessageAction)
        message_details = get_action.run(arguments={"user": "1111", "message_id": message_id})
        assert message_details["message_id"] == message_id
        assert "suspension" in message_details["body_preview"].lower()

        delete_action = configured_action(DeleteMessageAction)
        delete_action.run(arguments={"user": "1111", "message_id": message_id})


def test_resolve_message_item_index_out_of_range(configured_action):
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
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": "graph-item-id-1"}]},
        )

        resolve_action = configured_action(ResolveMessageAction)
        with pytest.raises(ValueError, match="out of range"):
            resolve_action.run(
                arguments={
                    "user": "1111",
                    "email_message_id": "<malicious-message-id@example.com>",
                    "item_index": 5,
                }
            )
