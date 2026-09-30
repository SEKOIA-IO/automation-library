from urllib.parse import unquote_plus

import pytest
import requests_mock

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_base import GraphAPIException
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.client import ApiClient


def test_search_messages_by_internet_message_id(configured_action, get_message_1):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [get_message_1]},
        )

        action = configured_action(SearchMessagesAction)
        action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>", "top": 5})

        request = mock.request_history[1]
        decoded_query = unquote_plus(request.url.split("?", maxsplit=1)[1])
        assert "$filter=internetMessageId eq '<sample-message-id@example.com>'" in decoded_query
        assert "$top=5" in decoded_query


def test_client_property_accepts_raw_string_client_secret():
    module = MicrosoftOutlookModule()
    module.configuration = {  # type: ignore[assignment]
        "tenant_id": "test_tenant_id",
        "client_id": "32747e7c-2eff-43ea-a9c7-e783b9d2f930",
        "client_secret": "client_secret",
    }

    action = SearchMessagesAction(module)
    assert isinstance(action.client, ApiClient)


def test_read_client_secret_accepts_raw_string_value():
    assert SearchMessagesAction._read_client_secret("client_secret") == "client_secret"


def test_read_client_secret_accepts_secretstr_like_value():
    class SecretLike:
        def get_secret_value(self):
            return "client_secret"

    assert SearchMessagesAction._read_client_secret(SecretLike()) == "client_secret"


def test_read_client_secret_rejects_non_string_secret_value():
    class BadSecretLike:
        def get_secret_value(self):
            return 123

    with pytest.raises(TypeError, match="Invalid client_secret type"):
        SearchMessagesAction._read_client_secret(BadSecretLike())


def test_read_client_secret_rejects_object_without_secret_getter():
    with pytest.raises(TypeError, match="Invalid client_secret type"):
        SearchMessagesAction._read_client_secret(object())


def test_search_messages_by_network_message_id(configured_action, get_message_1):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [get_message_1]},
        )

        action = configured_action(SearchMessagesAction)
        action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        request = mock.request_history[1]
        decoded_query = unquote_plus(request.url.split("?", maxsplit=1)[1])
        assert (
            "$filter=singleValueExtendedProperties/any(ep:ep/id eq "
            "'String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId' "
            "and ep/value eq '00000000-0000-4000-8000-000000000001')"
        ) in decoded_query
        assert (
            "$expand=singleValueExtendedProperties($filter=id eq "
            "'String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId')"
        ) in decoded_query


def test_search_messages_validation_error(configured_action):
    action = configured_action(SearchMessagesAction)
    try:
        action.run(arguments={"user": "1111"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Either email_message_id or email_local_id" in str(exc)


@pytest.mark.parametrize(
    "top,expected_match",
    [
        (0, "greater than or equal to 1"),
        (101, "less than or equal to 100"),
    ],
)
def test_search_messages_top_range_validation_error(configured_action, top, expected_match):
    action = configured_action(SearchMessagesAction)

    with pytest.raises(ValueError, match=expected_match):
        action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "top": top,
            }
        )


def test_search_messages_by_network_message_id_fallback_on_empty_result(configured_action):
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
                                "id": "graph-item-id-1",
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

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert len(result["messages"]) == 1
        assert result["messages"][0]["message_id"] == "graph-item-id-1"
        assert len(mock.request_history) == 3


def test_search_messages_by_network_message_id_fallback_on_inefficient_filter(configured_action):
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
                                "id": "graph-item-id-2",
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

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert len(result["messages"]) == 1
        assert result["messages"][0]["message_id"] == "graph-item-id-2"


def test_search_messages_omits_message_id_when_graph_id_is_not_string(configured_action):
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

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})

        assert len(result["messages"]) == 1
        assert "message_id" not in result["messages"][0]


def test_extract_network_message_id_returns_none_for_non_string_value():
    message = {
        "singleValueExtendedProperties": [
            {
                "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                "value": 123,
            }
        ]
    }

    assert SearchMessagesAction._extract_network_message_id(message) is None


def test_extract_network_message_id_returns_none_when_property_is_absent():
    message = {
        "singleValueExtendedProperties": [
            {
                "id": "String {11111111-1111-1111-1111-111111111111} Name OtherProperty",
                "value": "foo",
            }
        ]
    }

    assert SearchMessagesAction._extract_network_message_id(message) is None


def test_search_messages_by_network_message_id_raises_non_inefficient_filter_error(configured_action):
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

        action = configured_action(SearchMessagesAction)
        with pytest.raises(GraphAPIException, match="BadRequest"):
            action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})
