import base64
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from microsoft_outlook_modules.eml_parser import parse_msg_from_base64


def test_msg_metadata_terminators_are_removed_without_changing_attachment_bytes():
    payload = b"attachment\x00\x00"
    message = SimpleNamespace(
        header=None,
        subject="Subject\x00\x00",
        sender="Sender <sender@example.org>\x00",
        to="to@example.org\x00",
        cc="cc@example.org\x00",
        messageId="<id@example.org>\x00",
        date=datetime(2026, 11, 12, tzinfo=UTC),
        body="Body\x00",
        htmlBody=None,
        attachments=[
            SimpleNamespace(longFilename="file.txt\x00\x00", data=payload, mimetype="text/plain\x00"),
            SimpleNamespace(longFilename="\x00", shortFilename="fallback.txt\x00", data=b"", mimetype="\x00"),
        ],
        close=Mock(),
    )
    library = Mock()
    library.Message.return_value = message
    with patch.dict("sys.modules", {"extract_msg": library}):
        result = parse_msg_from_base64(base64.b64encode(b"test msg").decode())
    assert result["subject"] == "Subject"
    assert result["from"] == "Sender <sender@example.org>"
    assert result["to"] == "to@example.org" and result["cc"] == "cc@example.org"
    assert result["message_id"] == "<id@example.org>"
    assert result["body_plain"] == "Body\x00"
    assert result["nested_attachments"][0] == {
        "name": "file.txt",
        "content_type": "text/plain",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert result["nested_attachments"][1]["name"] == "fallback.txt"
    assert result["nested_attachments"][1]["content_type"] == "application/octet-stream"
    message.close.assert_called_once()
