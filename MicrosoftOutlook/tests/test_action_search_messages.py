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
        result = action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "max_messages_to_return": 5,
            }
        )

        assert result["message_ids"] == [get_message_1["id"]]
        assert result["user"] == "1111"
        assert result["query_type"] == "email_message_id"
        assert result["query_value"] == "<sample-message-id@example.com>"
        assert result["total_results"] == 1
        assert result["returned_count"] == 1
        assert result["has_more"] is False
        assert result["scan_limit_reached"] is False

        request = mock.request_history[1]
        decoded_query = unquote_plus(request.url.split("?", maxsplit=1)[1])
        assert "$filter=internetMessageId eq '<sample-message-id@example.com>'" in decoded_query
        assert "$top=5" in decoded_query


def test_search_messages_return_most_recent_first_adds_orderby(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": "graph-item-id-1", "internetMessageId": "<sample-message-id@example.com>"}]},
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "return_most_recent_first": True,
            }
        )

        assert result["message_ids"] == ["graph-item-id-1"]
        assert result["query_type"] == "email_message_id"
        assert result["query_value"] == "<sample-message-id@example.com>"

        request = mock.request_history[1]
        decoded_query = unquote_plus(request.url.split("?", maxsplit=1)[1])
        assert "$orderby=receivedDateTime desc" in decoded_query
        assert "$filter=receivedDateTime ge 1900-01-01T00:00:00Z and " in decoded_query
        assert decoded_query.index("receivedDateTime ge 1900-01-01T00:00:00Z") < decoded_query.index(
            "internetMessageId eq '<sample-message-id@example.com>'"
        )


def test_client_property_accepts_raw_string_client_secret():
    module = MicrosoftOutlookModule()
    module.configuration = {  # type: ignore[assignment]
        "tenant_id": "test_tenant_id",
        "client_id": "32747e7c-2eff-43ea-a9c7-e783b9d2f930",
        "client_secret": "client_secret",
    }

    action = SearchMessagesAction(module)
    assert isinstance(action.client, ApiClient)


@pytest.mark.parametrize(
    "client_secret_value,expected",
    [
        ("client_secret", "client_secret"),
    ],
)
def test_read_client_secret_accepts_supported_types(client_secret_value, expected):
    assert SearchMessagesAction._read_client_secret(client_secret_value) == expected


def test_read_client_secret_accepts_secretstr_like_value_object():
    class SecretLike:
        def get_secret_value(self):
            return "client_secret"

    assert SearchMessagesAction._read_client_secret(SecretLike()) == "client_secret"


@pytest.mark.parametrize(
    "client_secret_value",
    [
        pytest.param(object(), id="missing_secret_getter"),
    ],
)
def test_read_client_secret_rejects_unsupported_secret_types(client_secret_value):
    with pytest.raises(TypeError, match="Invalid client_secret type"):
        SearchMessagesAction._read_client_secret(client_secret_value)


def test_read_client_secret_rejects_non_string_secret_value():
    class BadSecretLike:
        def get_secret_value(self):
            return 123

    with pytest.raises(TypeError, match="Invalid client_secret type"):
        SearchMessagesAction._read_client_secret(BadSecretLike())


def test_search_messages_by_network_message_id(configured_action, get_message_1):
    payload = {
        **get_message_1,
        "singleValueExtendedProperties": [
            {
                "id": SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY,
                "value": "00000000-0000-4000-8000-000000000001",
            }
        ],
    }

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [payload]},
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert result["messages"][0]["message_id"] == get_message_1["id"]
        assert result["messages"][0]["network_message_id"] == "00000000-0000-4000-8000-000000000001"
        assert result["message_ids"] == [get_message_1["id"]]
        assert result["query_type"] == "email_local_id"
        assert result["query_value"] == "00000000-0000-4000-8000-000000000001"

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


def test_search_messages_with_combined_identifiers(configured_action, get_message_1):
    payload = {
        **get_message_1,
        "singleValueExtendedProperties": [
            {
                "id": SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY,
                "value": "00000000-0000-4000-8000-000000000001",
            }
        ],
    }

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [payload]},
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
            }
        )

        assert result["query_type"] == "combined"
        assert (
            result["query_value"]
            == "email_message_id=<sample-message-id@example.com>;email_local_id=00000000-0000-4000-8000-000000000001"
        )


def test_search_messages_validation_error(configured_action):
    action = configured_action(SearchMessagesAction)
    try:
        action.run(arguments={"user": "1111"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Either email_message_id or email_local_id" in str(exc)


@pytest.mark.parametrize(
    "max_messages_to_return,expected_match",
    [
        (0, "greater than or equal to 1"),
        (101, "less than or equal to 100"),
    ],
)
def test_search_messages_max_messages_to_return_range_validation_error(
    configured_action, max_messages_to_return, expected_match
):
    action = configured_action(SearchMessagesAction)

    with pytest.raises(ValueError, match=expected_match):
        action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "max_messages_to_return": max_messages_to_return,
            }
        )


@pytest.mark.parametrize(
    "initial_response",
    [
        {"status_code": 200, "json": {"value": []}},
        {
            "status_code": 400,
            "text": '{"error":{"code":"InefficientFilter","message":"The restriction or sort order is too complex for this operation."}}',
        },
    ],
    ids=["empty_result", "inefficient_filter"],
)
def test_search_messages_by_network_message_id_fallback(configured_action, initial_response):
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
                initial_response,
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
        assert result["message_ids"] == ["graph-item-id-2"]
        assert result["query_type"] == "email_local_id"
        assert result["query_value"] == "00000000-0000-4000-8000-000000000001"
        assert len(mock.request_history) == 3
        assert result["scan_limit_reached"] is False


def test_search_messages_fallback_ignores_empty_optional_identifier(configured_action):
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
                                "id": "graph-item-id-2",
                                "internetMessageId": "<sample-message-id@example.com>",
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
        result = action.run(
            arguments={
                "user": "1111",
                "email_message_id": "",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
            }
        )

        assert result["message_ids"] == ["graph-item-id-2"]
        assert result["messages"][0]["message_id"] == "graph-item-id-2"
        assert result["query_type"] == "email_local_id"
        assert result["query_value"] == "00000000-0000-4000-8000-000000000001"
        assert len(mock.request_history) == 3


def test_search_messages_by_network_message_id_fallback_paginates_until_match(configured_action):
    next_link = "https://graph.microsoft.com/v1.0/users/1111/messages?$skiptoken=abc123"

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
                                "id": "graph-item-id-unmatched",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                        "value": "00000000-0000-4000-8000-000000000099",
                                    }
                                ],
                            }
                        ],
                        "@odata.nextLink": next_link,
                    },
                },
            ],
        )
        mock.register_uri(
            "GET",
            next_link,
            status_code=200,
            json={
                "value": [
                    {
                        "id": "graph-item-id-match",
                        "singleValueExtendedProperties": [
                            {
                                "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                "value": "00000000-0000-4000-8000-000000000001",
                            }
                        ],
                    }
                ]
            },
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert result["message_ids"] == ["graph-item-id-match"]
        assert result["messages"][0]["message_id"] == "graph-item-id-match"
        assert len(mock.request_history) == 4

        fallback_first_page_request = mock.request_history[2]
        decoded_first_page_query = unquote_plus(fallback_first_page_request.url.split("?", maxsplit=1)[1])
        assert "$top=50" in decoded_first_page_query
        assert "$select=id,internetMessageId,subject,receivedDateTime,from,toRecipients" in decoded_first_page_query
        assert "$expand=singleValueExtendedProperties($filter=id eq " in decoded_first_page_query

        fallback_continuation_request = mock.request_history[3]
        assert fallback_continuation_request.url == next_link
        decoded_continuation_query = unquote_plus(fallback_continuation_request.url.split("?", maxsplit=1)[1])
        assert "$top=" not in decoded_continuation_query
        assert "$select=" not in decoded_continuation_query
        assert "$expand=" not in decoded_continuation_query
        assert "$orderby=" not in decoded_continuation_query


def test_search_messages_fallback_sets_has_more_for_truncated_last_page(configured_action):
    def _match(message_id: str) -> dict[str, object]:
        return {
            "id": message_id,
            "singleValueExtendedProperties": [
                {
                    "id": SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY,
                    "value": "00000000-0000-4000-8000-000000000001",
                }
            ],
        }

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
                            _match("graph-item-id-1"),
                            _match("graph-item-id-2"),
                        ]
                    },
                },
            ],
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(
            arguments={
                "user": "1111",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
                "max_messages_to_return": 1,
            }
        )

        assert result["message_ids"] == ["graph-item-id-1"]
        assert len(result["messages"]) == 1
        assert result["has_more"] is True
        assert result["scan_limit_reached"] is False


@pytest.mark.parametrize(
    "scenario,next_link,expected_has_more,expected_request_count",
    [
        (
            "intra_page_overflow",
            "https://graph.microsoft.com/v1.0/users/1111/messages?$skiptoken=budget-overflow",
            False,
            4,
        ),
        (
            "cap_hit_with_next_link",
            "https://graph.microsoft.com/v1.0/users/1111/messages?$skiptoken=cap-reached",
            True,
            3,
        ),
    ],
)
def test_search_messages_fallback_scan_limit_signals(
    configured_action,
    scenario,
    next_link,
    expected_has_more,
    expected_request_count,
):
    def _network_message(value: str, message_id: str) -> dict[str, object]:
        return {
            "id": message_id,
            "singleValueExtendedProperties": [
                {
                    "id": SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY,
                    "value": value,
                }
            ],
        }

    if scenario == "intra_page_overflow":
        first_page = [_network_message("00000000-0000-4000-8000-000000000099", f"unmatched-{i}") for i in range(995)]
        continuation_page = [
            _network_message("00000000-0000-4000-8000-000000000099", f"overflow-unmatched-{i}") for i in range(5)
        ] + [_network_message("00000000-0000-4000-8000-000000000001", "overflow-match")]
    else:
        first_page = [_network_message("00000000-0000-4000-8000-000000000099", f"unmatched-{i}") for i in range(1000)]
        continuation_page = None

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
                        "value": first_page,
                        "@odata.nextLink": next_link,
                    },
                },
            ],
        )
        if continuation_page is not None:
            mock.register_uri(
                "GET",
                next_link,
                status_code=200,
                json={"value": continuation_page},
            )

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_local_id": "00000000-0000-4000-8000-000000000001"})

        assert result["message_ids"] == []
        assert result["messages"] == []
        assert result["has_more"] is expected_has_more
        assert result["scan_limit_reached"] is True
        assert len(mock.request_history) == expected_request_count


@pytest.mark.parametrize(
    "arguments,fallback_value,expected_message_ids,expected_query_type",
    [
        (
            {
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "return_most_recent_first": True,
            },
            [
                {
                    "id": "graph-item-id-3",
                    "internetMessageId": "<sample-message-id@example.com>",
                }
            ],
            ["graph-item-id-3"],
            "email_message_id",
        ),
        (
            {
                "user": "1111",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
            },
            [],
            [],
            "email_local_id",
        ),
    ],
    ids=["match_found", "no_match"],
)
def test_search_messages_fallback_on_inefficient_filter(
    configured_action,
    arguments,
    fallback_value,
    expected_message_ids,
    expected_query_type,
):
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
                    "json": {"value": fallback_value},
                },
            ],
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments=arguments)

        assert result["message_ids"] == expected_message_ids
        assert result["query_type"] == expected_query_type
        assert len(result["messages"]) == len(expected_message_ids)
        assert len(mock.request_history) == 3


@pytest.mark.parametrize(
    "initial_response",
    [
        {"status_code": 200, "json": {"value": []}},
        {
            "status_code": 400,
            "text": '{"error":{"code":"InefficientFilter","message":"The restriction or sort order is too complex for this operation."}}',
        },
    ],
    ids=["empty_result", "inefficient_filter"],
)
def test_search_messages_combined_identifiers_fallback_applies_and_filter(configured_action, initial_response):
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
                initial_response,
                {
                    "status_code": 200,
                    "json": {
                        "value": [
                            {
                                "id": "graph-item-id-mismatch",
                                "internetMessageId": "<different-message-id@example.com>",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                        "value": "00000000-0000-4000-8000-000000000001",
                                    }
                                ],
                            },
                            {
                                "id": "graph-item-id-match",
                                "internetMessageId": "<sample-message-id@example.com>",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                                        "value": "00000000-0000-4000-8000-000000000001",
                                    }
                                ],
                            },
                        ]
                    },
                },
            ],
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
            }
        )

        assert result["message_ids"] == ["graph-item-id-match"]
        assert len(result["messages"]) == 1
        assert result["messages"][0]["message_id"] == "graph-item-id-match"
        assert result["query_type"] == "combined"


@pytest.mark.parametrize(
    "return_most_recent_first,order_by_expected",
    [
        (False, False),
        (True, True),
    ],
    ids=["without_orderby", "with_orderby"],
)
def test_search_messages_fallback_orderby_behavior(
    configured_action,
    return_most_recent_first,
    order_by_expected,
):
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
        result = action.run(
            arguments={
                "user": "1111",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
                "return_most_recent_first": return_most_recent_first,
            }
        )

        assert result["message_ids"] == ["graph-item-id-1"]
        fallback_request = mock.request_history[2]
        decoded_query = unquote_plus(fallback_request.url.split("?", maxsplit=1)[1])
        assert ("$orderby=receivedDateTime desc" in decoded_query) is order_by_expected


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
        assert result["messages"] == [{"subject": "test-subject"}]
        assert result["message_ids"] == []


def test_search_messages_returns_empty_selection_when_no_results(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": []},
        )

        action = configured_action(SearchMessagesAction)
        result = action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})

        assert result == {
            "user": "1111",
            "query_type": "email_message_id",
            "query_value": "<sample-message-id@example.com>",
            "message_ids": [],
            "messages": [],
            "total_results": 0,
            "returned_count": 0,
            "has_more": False,
            "scan_limit_reached": False,
        }


def test_search_messages_rejects_removed_item_index_input(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": "graph-item-id-1"}]},
        )

        action = configured_action(SearchMessagesAction)
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            action.run(
                arguments={
                    "user": "1111",
                    "email_message_id": "<sample-message-id@example.com>",
                    "item_index": 2,
                }
            )


@pytest.mark.parametrize(
    "message",
    [
        {
            "singleValueExtendedProperties": [
                {
                    "id": "String {41F28F13-83F4-4114-A584-EEDB5A6B0BFF} Name NetworkMessageId",
                    "value": 123,
                }
            ]
        },
        {
            "singleValueExtendedProperties": [
                {
                    "id": "String {11111111-1111-1111-1111-111111111111} Name OtherProperty",
                    "value": "foo",
                }
            ]
        },
    ],
)
def test_extract_network_message_id_returns_none_when_unusable(message):
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
