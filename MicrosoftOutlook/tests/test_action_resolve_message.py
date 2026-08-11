import pytest
import requests_mock
from urllib.parse import unquote_plus

from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction


@pytest.mark.parametrize(
    "arguments,expected_match",
    [
        ({"user": "1111"}, "Either email_message_id or email_local_id"),
        ({"user": "1111", "email_message_id": "<sample-message-id@example.com>", "item_index": -1}, "item_index"),
        (
            {"user": "1111", "email_message_id": "<sample-message-id@example.com>", "top": 0},
            "greater than or equal to 1",
        ),
        (
            {"user": "1111", "email_message_id": "<sample-message-id@example.com>", "top": 101},
            "less than or equal to 100",
        ),
    ],
)
def test_resolve_message_validation_errors(configured_action, arguments, expected_match):
    action = configured_action(ResolveMessageAction)
    with pytest.raises(ValueError, match=expected_match):
        action.run(arguments=arguments)


def test_resolve_message_not_found_error(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("GET", "https://graph.microsoft.com/v1.0/users/1111/messages", json={"value": []})

        action = configured_action(ResolveMessageAction)
        with pytest.raises(ValueError, match="No message found"):
            action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})


def test_resolve_message_defaults_to_first_result(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": "graph-item-id-1"}, {"id": "graph-item-id-2"}]},
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})

        assert result["graph_message_id"] == "graph-item-id-1"
        assert result["selected_index"] == 0
        assert result["total_results"] == 2


def test_resolve_message_most_recent_and_item_index(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={
                "value": [
                    {"id": "graph-item-id-1", "receivedDateTime": "2026-08-10T09:20:25Z"},
                    {"id": "graph-item-id-2", "receivedDateTime": "2026-08-10T09:10:25Z"},
                ]
            },
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
                "most_recent": True,
                "item_index": 1,
            }
        )

        request = mock.request_history[1]
        decoded_query = unquote_plus(request.url.split("?", maxsplit=1)[1])
        assert "$orderby=receivedDateTime desc" in decoded_query
        assert result["graph_message_id"] == "graph-item-id-2"
