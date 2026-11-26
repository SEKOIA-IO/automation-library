import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest


@pytest.fixture
def sample_graph_message():
    return {
        "id": "AAMkAGI2TG93AAA=",
        "subject": "Suspicious: Reset your password",
        "from": {"emailAddress": {"name": "Attacker", "address": "attacker@evil.com"}},
        "sender": {"emailAddress": {"name": "Attacker", "address": "attacker@evil.com"}},
        "replyTo": [{"emailAddress": {"name": "", "address": "reply@evil.com"}}],
        "toRecipients": [{"emailAddress": {"name": "Victim", "address": "victim@company.com"}}],
        "ccRecipients": [],
        "bccRecipients": [],
        "receivedDateTime": "2026-04-28T10:00:00Z",
        "sentDateTime": "2026-04-28T09:59:00Z",
        "body": {
            "contentType": "html",
            "content": "<html><body>Click <a href='https://evil.com/phish'>here</a></body></html>",
        },
        "bodyPreview": "Click here",
        "hasAttachments": True,
        "isRead": False,
        "importance": "normal",
        "internetMessageId": "<msg123@evil.com>",
        "internetMessageHeaders": [
            {"name": "X-Mailer", "value": "EvilMailer/1.0"},
            {"name": "Return-Path", "value": "attacker@evil.com"},
        ],
        "webLink": "https://outlook.office365.com/owa/?ItemID=AAMkAGI2TG93AAA%3D",
        "conversationId": "conv-001",
        "parentFolderId": "inbox-folder-id",
        "flag": {"flagStatus": "notFlagged"},
        "attachments": [],
    }


@pytest.fixture
def sample_eml_b64():
    """Generate a base64-encoded sample EML file."""
    msg = MIMEMultipart()
    msg["Subject"] = "Original phishing: Win a prize!"
    msg["From"] = "phisher@evil.com"
    msg["To"] = "user@company.com"
    msg["Reply-To"] = "phisher-reply@evil.com"
    msg["Date"] = "Mon, 28 Apr 2026 08:00:00 +0000"
    msg["Message-ID"] = "<original@evil.com>"
    msg["Return-Path"] = "<bounce@evil.com>"
    msg["X-Originating-IP"] = "[192.168.1.100]"
    msg["Authentication-Results"] = (
        "mx.google.com; spf=fail smtp.mailfrom=evil.com; "
        "dkim=pass header.d=evil.com; dmarc=fail action=none header.from=evil.com"
    )
    msg["Received"] = "from mail.evil.com (192.168.1.100) by mx.company.com; Mon, 28 Apr 2026 08:00:01 +0000"

    body = MIMEText(
        '<html><body><a href="https://evil.com/steal">Click here</a></body></html>',
        "html",
    )
    msg.attach(body)

    plain = MIMEText("Click here to win a prize! https://evil.com/plain-link", "plain")
    msg.attach(plain)

    return base64.b64encode(msg.as_bytes()).decode("ascii")


@pytest.fixture
def mock_token_response():
    return {"access_token": "fake-access-token-123", "token_type": "Bearer", "expires_in": 3600}


@pytest.fixture
def sample_attachment(sample_eml_b64):
    return {
        "id": "att-001",
        "name": "reported_phish.eml",
        "contentType": "message/rfc822",
        "size": 2048,
        "contentBytes": sample_eml_b64,
    }
