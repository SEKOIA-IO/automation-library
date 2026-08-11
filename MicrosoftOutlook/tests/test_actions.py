from typing import Type

import pytest
import requests_mock
from requests import HTTPError

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_base import GraphAPIException, MicrosoftGraphActionBase
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.action_send_message import SendMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction


def configured_action(action: Type[MicrosoftGraphActionBase]):
    module = MicrosoftOutlookModule()
    module.configuration = {
        "tenant_id": "test_tenant_id",
        "client_id": "32747e7c-2eff-43ea-a9c7-e783b9d2f930",
        "client_secret": "client_secret",
    }
    a = action(module)
    return a


@pytest.fixture
def get_message_1():
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('7f180cbb-a5ae-457c-b7e8-6f5b42ba33e7')/messages/$entity",
        "@odata.etag": 'W/"CQAAABYAAAC4ofQHEIqCSbQPot83AFcbAAAnjjuZ"',
        "id": "AAMkADhMGAAA=",
        "createdDateTime": "2018-09-09T03:15:05Z",
        "lastModifiedDateTime": "2018-09-09T03:15:08Z",
        "changeKey": "CQAAABYAAAC4ofQHEIqCSbQPot83AFcbAAAnjjuZ",
        "categories": [],
        "receivedDateTime": "2018-09-09T03:15:08Z",
        "sentDateTime": "2018-09-09T03:15:06Z",
        "hasAttachments": False,
        "internetMessageId": "<sample-message-id@example.com>",
        "subject": "9/9/2018: concert",
        "bodyPreview": "The group represents Nevada.",
        "importance": "normal",
        "parentFolderId": "AAMkADcbAAAAAAEJAAA=",
        "conversationId": "AAQkADOUpag6yWs=",
        "isDeliveryReceiptRequested": False,
        "isReadReceiptRequested": False,
        "isRead": True,
        "isDraft": False,
        "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkADMGAAA%3D&exvsurl=1&viewmodel=ReadMessageItem",
        "inferenceClassification": "focused",
        "body": {
            "contentType": "html",
            "content": '<html>\r\n<head>\r\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\r\n<meta content="text/html; charset=us-ascii">\r\n</head>\r\n<body>\r\nThe group represents Nevada.\r\n</body>\r\n</html>\r\n',
        },
        "sender": {"emailAddress": {"name": "Example Sender", "address": "sender@example.com"}},
        "from": {"emailAddress": {"name": "Example Sender", "address": "sender@example.com"}},
        "toRecipients": [{"emailAddress": {"name": "Example Recipient", "address": "recipient@example.com"}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "replyTo": [],
        "flag": {"flagStatus": "notFlagged"},
    }


@pytest.fixture
def message_2():
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('7f180cbb-a5ae-457c-b7e8-6f5b42ba33e7')/messages/$entity",
        "@odata.etag": 'W/"CQAAABYAAAC4ofQHEIqCSbQPot83AFcbAAAnjjuZ"',
        "id": "AAMkADhMGAAA=",
        "createdDateTime": "2018-09-09T03:15:05Z",
        "lastModifiedDateTime": "2018-09-09T03:15:08Z",
        "changeKey": "CQAAABYAAAC4ofQHEIqCSbQPot83AFcbAAAnjjuZ",
        "categories": [],
        "receivedDateTime": "2018-09-09T03:15:08Z",
        "sentDateTime": "2018-09-09T03:15:06Z",
        "hasAttachments": False,
        "internetMessageId": "<sample-message-id@example.com>",
        "subject": "Changed Subject",
        "bodyPreview": "The group represents Nevada.",
        "importance": "normal",
        "parentFolderId": "AAMkADcbAAAAAAEJAAA=",
        "conversationId": "AAQkADOUpag6yWs=",
        "isDeliveryReceiptRequested": False,
        "isReadReceiptRequested": False,
        "isRead": True,
        "isDraft": False,
        "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkADMGAAA%3D&exvsurl=1&viewmodel=ReadMessageItem",
        "inferenceClassification": "focused",
        "body": {
            "contentType": "html",
            "content": '<html>\r\n<head>\r\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\r\n<meta content="text/html; charset=us-ascii">\r\n</head>\r\n<body>\r\nThe group represents Nevada.\r\n</body>\r\n</html>\r\n',
        },
        "sender": {"emailAddress": {"name": "Example Sender", "address": "sender@example.com"}},
        "from": {"emailAddress": {"name": "Example Sender", "address": "sender@example.com"}},
        "toRecipients": [{"emailAddress": {"name": "Example Recipient", "address": "recipient@example.com"}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "replyTo": [],
        "flag": {"flagStatus": "notFlagged"},
    }


def test_get_message(get_message_1):
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

        mock.register_uri("GET", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", json=get_message_1)

        action = configured_action(GetMessageAction)
        action.run(arguments={"user": "1111", "message_id": "2222"})


def test_forward_message():
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
            "POST", "https://graph.microsoft.com/v1.0/users/1111/messages/2222/forward", status_code=202, content=b""
        )

        action = configured_action(ForwardMessageAction)
        action.run(arguments={"user": "1111", "message_id": "2222", "recipients": ["john.doe@example.com"]})


def test_delete_message():
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
            "DELETE", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", status_code=204, content=b""
        )

        action = configured_action(DeleteMessageAction)
        action.run(arguments={"user": "1111", "message_id": "2222"})


def test_update_message(message_2):
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
            "PATCH", "https://graph.microsoft.com/v1.0/users/1111/messages/2222", status_code=204, json=message_2
        )

        action = configured_action(UpdateMessageAction)
        action.run(arguments={"user": "1111", "message_id": "2222", "subject": "Changed Subject"})


def test_send_message(message_2):
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

        mock.register_uri("POST", "https://graph.microsoft.com/v1.0/users/1111/sendMail", status_code=202)

        action = configured_action(SendMessageAction)
        action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "sender": "john.doe@example.com",
                "from": "john.doe@example.com",
                "recipients": ["jane.doe@example.com"],
            }
        )


def test_send_message_with_all_optional_fields():
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

        mock.register_uri("POST", "https://graph.microsoft.com/v1.0/users/1111/sendMail", status_code=202)

        action = configured_action(SendMessageAction)
        action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "content_type": "html",
                "sender": "sender@example.com",
                "from": "owner@example.com",
                "recipients": ["to1@example.com", "to2@example.com"],
                "cc": ["cc@example.com"],
                "bcc": ["bcc@example.com"],
                "importance": "High",
                "save_to_sent_items": False,
            }
        )

        request = mock.request_history[1]
        payload = request.json()
        assert payload["saveToSentItems"] is False
        assert payload["message"]["importance"] == "High"
        assert payload["message"]["body"]["contentType"] == "html"
        assert len(payload["message"]["toRecipients"]) == 2
        assert payload["message"]["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
        assert payload["message"]["bccRecipients"][0]["emailAddress"]["address"] == "bcc@example.com"


def test_send_message_returns_empty_dict_when_response_is_not_json():
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
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/sendMail",
            status_code=202,
            content=b"",
        )

        action = configured_action(SendMessageAction)
        result = action.run(arguments={"user": "1111"})
        assert result == {}


def test_update_message_with_all_optional_fields(message_2):
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


@pytest.mark.parametrize(
    "status_code,body,expected_exception",
    [
        (400, '{"error":{"code":"ErrorInvalidIdMalformed","message":"Id is malformed."}}', GraphAPIException),
        (500, "server_error", HTTPError),
    ],
)
def test_action_error_handling(status_code, body, expected_exception):
    class FakeResponse:
        def __init__(self, response_status_code: int, response_text: str):
            self.ok = False
            self.status_code = response_status_code
            self.text = response_text
            self.reason = "Bad Request" if response_status_code == 400 else "Internal Server Error"

        def raise_for_status(self):
            raise HTTPError(f"{self.status_code} {self.reason}")

    action = configured_action(GetMessageAction)
    action.log = lambda **_kwargs: None
    with pytest.raises(expected_exception):
        action.handle_response(FakeResponse(status_code, body))


def test_search_messages_by_internet_message_id(get_message_1):
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
            json={"value": [get_message_1]},
        )

        action = configured_action(SearchMessagesAction)
        action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<sample-message-id@example.com>",
                "top": 5,
            }
        )

        request = mock.request_history[1]
        assert request.qs["$filter"] == [
            "internetmessageid eq '<sample-message-id@example.com>'"
        ]
        assert request.qs["$top"] == ["5"]


def test_search_messages_by_network_message_id(get_message_1):
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
            json={"value": [get_message_1]},
        )

        action = configured_action(SearchMessagesAction)
        action.run(
            arguments={
                "user": "1111",
                "email_local_id": "00000000-0000-4000-8000-000000000001",
            }
        )

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


@pytest.mark.parametrize(
    "arguments,expected_match",
    [
        ({"user": "1111"}, "Either email_message_id or email_local_id"),
        ({"user": "1111", "email_message_id": "<sample-message-id@example.com>", "item_index": -1}, "item_index"),
    ],
)
def test_resolve_message_validation_errors(arguments, expected_match):
    action = configured_action(ResolveMessageAction)
    with pytest.raises(ValueError, match=expected_match):
        action.run(arguments=arguments)


def test_search_messages_validation_error():
    action = configured_action(SearchMessagesAction)
    with pytest.raises(ValueError, match="Either email_message_id or email_local_id"):
        action.run(arguments={"user": "1111"})


def test_resolve_message_not_found_error():
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
            json={"value": []},
        )

        action = configured_action(ResolveMessageAction)
        with pytest.raises(ValueError, match="No message found"):
            action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})


def test_resolve_message_defaults_to_first_result():
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
            json={"value": [{"id": "graph-item-id-1"}, {"id": "graph-item-id-2"}]},
        )

        action = configured_action(ResolveMessageAction)
        result = action.run(arguments={"user": "1111", "email_message_id": "<sample-message-id@example.com>"})

        assert result["graph_message_id"] == "graph-item-id-1"
        assert result["selected_index"] == 0
        assert result["total_results"] == 2


def test_resolve_message_most_recent_and_item_index():
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
        assert request.qs["$orderby"] == ["receiveddatetime desc"]
        assert result["graph_message_id"] == "graph-item-id-2"
