from urllib.parse import unquote_plus

import pytest
import requests_mock

from microsoft_outlook_modules.action_base import GraphAPIException
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


def test_resolve_message_raises_when_selected_message_id_is_not_string(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": None, "subject": "test-subject"}]},
        )

        action = configured_action(ResolveMessageAction)
        with pytest.raises(ValueError, match="Unable to resolve a valid string message_id"):
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

        assert result["message_id"] == "graph-item-id-1"
        assert result["selected_index"] == 0
        assert result["total_results"] == 2


def test_resolve_message_omits_message_id_for_candidates_with_non_string_id(configured_action):
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
                    {"id": "graph-item-id-1", "subject": "selected"},
                    {"id": None, "subject": "secondary"},
                ]
            },
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})

        assert result["message_id"] == "graph-item-id-1"
        assert result["messages"][0]["message_id"] == "graph-item-id-1"
        assert "message_id" not in result["messages"][1]


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
        assert result["message_id"] == "graph-item-id-2"


def test_resolve_message_by_network_message_id_fallback_on_empty_result(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            [
                {"status_code": 200, "json": {"value": []}},
                {
                    "status_code": 200,
                    "json": {
                        "value": [
                            {
                                "id": "graph-item-id-3",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                        "value": "00000000-0000-4000-8000-000000000001",
                                    }
                                ],
                            }
                        ]
                    },
                },
            ],
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert result["message_id"] == "graph-item-id-3"
        assert result["total_results"] == 1


def test_resolve_message_by_network_message_id_fallback_on_inefficient_filter(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            [
                {
                    "status_code": 400,
                    "text": '{"error":{"code":"InefficientFilter","message":"The restriction or sort order is too complex for this operation."}}',
                },
                {
                    "status_code": 200,
                    "json": {
                        "value": [
                            {
                                "id": "graph-item-id-4",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                        "value": "00000000-0000-4000-8000-000000000001",
                                    }
                                ],
                            }
                        ]
                    },
                },
            ],
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert result["message_id"] == "graph-item-id-4"
        assert result["total_results"] == 1


def test_extract_network_message_id_returns_none_for_non_string_value():
    message = {
        "singleValueExtendedProperties": [
            {
                "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                "value": 123,
            }
        ]
    }

    assert ResolveMessageAction._extract_network_message_id(message) is None


def test_extract_network_message_id_returns_none_when_property_is_absent():
    message = {
        "singleValueExtendedProperties": [
            {
                "id": "String {11111111-1111-1111-1111-111111111111} Name OtherProperty",
                "value": "foo",
            }
        ]
    }

    assert ResolveMessageAction._extract_network_message_id(message) is None


def test_resolve_message_by_network_message_id_raises_non_inefficient_filter_error(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            status_code=400,
            text='{"error":{"code":"BadRequest","message":"boom"}}',
        )

        action = configured_action(ResolveMessageAction)
        with pytest.raises(GraphAPIException, match="BadRequest"):
            action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})
