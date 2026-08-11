import requests_mock

from microsoft_outlook_modules.action_search_messages import SearchMessagesAction


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
        assert request.qs["$filter"] == ["internetmessageid eq '<sample-message-id@example.com>'"]
        assert request.qs["$top"] == ["5"]


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
        assert request.qs["$filter"] == [
            "singlevalueextendedproperties/any(ep:ep/id eq "
            "'string {41f28f13-83f4-4114-a584-eedb5a6b0bff} name networkmessageid' "
            "and ep/value eq '00000000-0000-4000-8000-000000000001')"
        ]
        assert request.qs["$expand"] == [
            "singlevalueextendedproperties($filter=id eq "
            "'string {41f28f13-83f4-4114-a584-eedb5a6b0bff} name networkmessageid')"
        ]


def test_search_messages_validation_error(configured_action):
    action = configured_action(SearchMessagesAction)
    try:
        action.run(arguments={"user": "1111"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "Either email_message_id or email_local_id" in str(exc)
