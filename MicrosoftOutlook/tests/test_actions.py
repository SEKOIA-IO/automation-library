from typing import Type

import pytest
import requests_mock

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_base import MicrosoftGraphActionBase
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
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
        "internetMessageId": "<MWHPR6E1BE060@MWHPR1120.namprd22.prod.outlook.com>",
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
        "sender": {"emailAddress": {"name": "Adele Vance", "address": "adelev@contoso.com"}},
        "from": {"emailAddress": {"name": "Adele Vance", "address": "adelev@contoso.com"}},
        "toRecipients": [{"emailAddress": {"name": "Alex Wilber", "address": "AlexW@contoso.com"}}],
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
        "internetMessageId": "<MWHPR6E1BE060@MWHPR1120.namprd22.prod.outlook.com>",
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
        "sender": {"emailAddress": {"name": "Adele Vance", "address": "adelev@contoso.com"}},
        "from": {"emailAddress": {"name": "Adele Vance", "address": "adelev@contoso.com"}},
        "toRecipients": [{"emailAddress": {"name": "Alex Wilber", "address": "AlexW@contoso.com"}}],
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
