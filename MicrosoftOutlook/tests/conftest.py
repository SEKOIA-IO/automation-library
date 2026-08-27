from collections.abc import Callable
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_base import MicrosoftGraphActionBase


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def configured_action() -> Callable[[type[MicrosoftGraphActionBase]], MicrosoftGraphActionBase]:
    def _configured_action(action_cls: type[MicrosoftGraphActionBase]) -> MicrosoftGraphActionBase:
        module = MicrosoftOutlookModule()
        module.configuration = {  # type: ignore[assignment]
            "tenant_id": "test_tenant_id",
            "client_id": "32747e7c-2eff-43ea-a9c7-e783b9d2f930",
            "client_secret": "client_secret",
        }
        return action_cls(module)

    return _configured_action


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
