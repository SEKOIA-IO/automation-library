from typing import Type

import pytest
import requests_mock

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_base import MicrosoftGraphActionBase
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction


def configured_action(action: Type[MicrosoftGraphActionBase]):
    module = MicrosoftOutlookModule()
    module.configuration = {
        "tenant_id": "test_tenant_id",
        "client_id": "32747e7c-2eff-43ea-a9c7-e783b9d2f930",
        "client_secret": "client_secret",
    }
    return action(module)


@pytest.mark.parametrize(
    "message_identifier",
    [
        {"email_message_id": "<malicious-message-id@example.com>"},
        {"email_local_id": "00000000-0000-4000-8000-000000000123"},
    ],
)
def test_playbook_workflow_detect_confirm_resolve_delete(message_identifier):
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
        assert len(search_result["value"]) == 1
        assert "urgent" in search_result["value"][0]["subject"].lower()

        resolve_action = configured_action(ResolveMessageAction)
        resolve_result = resolve_action.run(arguments={"user": "1111", **message_identifier})
        graph_message_id = resolve_result["graph_message_id"]
        assert graph_message_id == "graph-item-id-1"

        get_action = configured_action(GetMessageAction)
        message_details = get_action.run(arguments={"user": "1111", "message_id": graph_message_id})
        assert message_details["id"] == graph_message_id
        assert "suspension" in message_details["bodyPreview"].lower()

        delete_action = configured_action(DeleteMessageAction)
        delete_action.run(arguments={"user": "1111", "message_id": graph_message_id})


def test_resolve_message_item_index_out_of_range():
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
