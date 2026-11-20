"""Tests for EML parsing."""

import base64
import hashlib
from email import policy
from email.message import EmailMessage
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from microsoft_outlook_modules.eml_parser import _extract_urls, parse_eml_from_base64, parse_msg_from_base64


def parse_message(message):
    return parse_eml_from_base64(base64.b64encode(message.as_bytes()).decode("ascii"))


class TestAttachmentBytes:
    @pytest.mark.parametrize("cte", ["base64", "quoted-printable", "8bit"])
    def test_text_attachment_hashes_original_decoded_bytes(self, cte):
        message = EmailMessage(policy=policy.SMTP)
        message.set_content("Message body")
        payload = b"Compte rendu caf\xe9\r\n"
        message.add_attachment(payload, maintype="text", subtype="plain", filename="report.txt", cte=cte)
        message.get_payload()[-1].set_param("charset", "iso-8859-1")

        result = parse_message(message)

        assert result["nested_attachments"] == [
            {
                "name": "report.txt",
                "content_type": "text/plain",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "content_id": "",
                "content_disposition": "attachment",
                "is_inline": False,
            }
        ]
        assert result["body_plain"].strip() == "Message body"

    @pytest.mark.parametrize("subtype,payload", [("octet-stream", b"\x00\xff\x01"), ("octet-stream", b"")])
    def test_binary_and_empty_attachments(self, subtype, payload):
        message = EmailMessage()
        message.set_content("Message body")
        message.add_attachment(payload, maintype="application", subtype=subtype, filename="file.bin")

        attachment = parse_message(message)["nested_attachments"][0]

        assert attachment["size"] == len(payload)
        assert attachment["sha256"] == hashlib.sha256(payload).hexdigest()

    @pytest.mark.parametrize("subtype", ["plain", "html"])
    def test_text_attachment_is_not_used_as_message_body(self, subtype):
        message = EmailMessage()
        message.make_mixed()
        message.add_attachment(b"https://attachment.example/", maintype="text", subtype=subtype, filename="file.txt")
        body = EmailMessage()
        body.set_content("Actual message body")
        message.attach(body)

        result = parse_message(message)

        assert result["body_plain"].strip() == "Actual message body"
        assert result["body_html"] == ""
        assert result["urls"] == []
        assert len(result["nested_attachments"]) == 1

    def test_attached_message_does_not_replace_outer_body(self):
        original = EmailMessage()
        original.set_content("Attached email body")
        message = EmailMessage()
        message.make_mixed()
        message.add_attachment(original, filename="original.eml")
        body = EmailMessage()
        body.set_content("Outer body")
        message.attach(body)

        result = parse_message(message)

        assert result["body_plain"].strip() == "Outer body"
        assert result["nested_attachments"][0]["name"] == "original.eml"
        assert result["nested_attachments"][0]["size"] is None
        assert result["nested_attachments"][0]["sha256"] is None
        assert result["nested_attachments"][0]["processing_error"]


class TestExtractURLs:
    def test_html_attributes_decode_entities_and_preserve_spaces(self):
        html = (
            '<a href="https://safe.example/?url=https%3A%2F%2Fexample.com%2F&amp;data=123">Link</a>'
            '<img src="https://example.com/images/Header Reveal.png?version=0">'
        )
        assert _extract_urls(html, "") == [
            "https://safe.example/?url=https%3A%2F%2Fexample.com%2F&data=123",
            "https://example.com/images/Header%20Reveal.png?version=0",
        ]

    def test_removes_prose_delimiters_and_deduplicates_across_bodies(self):
        assert _extract_urls(
            '<img src="https://example.com/image.png"><a href="https://example.com/">Website</a>',
            "[https://example.com/image.png] <https://example.com/> (https://example.org/path).",
        ) == ["https://example.com/image.png", "https://example.com/", "https://example.org/path"]

    def test_preserves_balanced_brackets_and_encoded_url_data(self):
        assert _extract_urls("", "https://[::1]/ https://example.com/a_(b) https://example.com/?x=%26amp%3B") == [
            "https://[::1]/",
            "https://example.com/a_(b)",
            "https://example.com/?x=%26amp%3B",
        ]

    def test_decodes_html_entities_only_once(self):
        assert _extract_urls('<a href="https://example.com/?a=1&amp;amp;b=2">Link</a>', "") == [
            "https://example.com/?a=1&amp;b=2"
        ]

    def test_ignores_markup_urls_and_non_http_attributes(self):
        html = (
            '<!DOCTYPE html PUBLIC "x" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml"><style>/* https://style.example/ */</style>'
            '<script>"https://script.example/"</script><a href="javascript:alert(1)">Ignore</a>'
            '<a href="https://example.com/">https://example.com/</a></html>'
        )
        assert _extract_urls(html, "") == ["https://example.com/"]

    def test_outlook_report_keeps_original_and_rewritten_urls(self):
        message = EmailMessage()
        message.set_content("Documentation: https://docs.sekoia.com/\nReference: https://example.com/")
        message.add_alternative(
            '<a href="https://safe.example/?url=https%3A%2F%2Fdocs.sekoia.com%2F&amp;data=123" '
            'originalsrc="https://docs.sekoia.com/">Documentation</a>'
            '<a href="https://example.com/">Reference</a>',
            subtype="html",
        )
        message.add_attachment(b"Compte rendu\n", maintype="text", subtype="plain", filename="compte-rendu.txt")

        result = parse_message(message)

        assert result["urls"] == [
            "https://safe.example/?url=https%3A%2F%2Fdocs.sekoia.com%2F&data=123",
            "https://docs.sekoia.com/",
            "https://example.com/",
        ]
        assert result["nested_attachments"][0]["sha256"] == hashlib.sha256(b"Compte rendu\n").hexdigest()

    def test_msg_parser_uses_same_url_extraction(self):
        msg = MagicMock()
        msg.body = "[https://example.com/image.png]"
        msg.htmlBody = b'<img src="https://example.com/image.png"><a href="https://example.com/?a=1&amp;b=2">Link</a>'
        msg.attachments = []
        library = MagicMock()
        library.Message.return_value = msg

        with patch.dict("sys.modules", {"extract_msg": library}):
            result = parse_msg_from_base64(base64.b64encode(b"msg").decode())

        assert result["urls"] == ["https://example.com/image.png", "https://example.com/?a=1&b=2"]


class TestParseEml:
    def test_parse_eml_basic(self, sample_eml_b64):
        result = parse_eml_from_base64(sample_eml_b64)

        assert result["subject"] == "Original phishing: Win a prize!"
        assert result["from"] == "phisher@evil.com"
        assert result["to"] == "user@company.com"
        assert result["message_id"] == "<original@evil.com>"
        assert "multipart" in result["content_type"]

    def test_parse_eml_extracts_urls(self, sample_eml_b64):
        result = parse_eml_from_base64(sample_eml_b64)

        assert "https://evil.com/steal" in result["urls"]
        # URL from plain-text body should also be extracted
        assert "https://evil.com/plain-link" in result["urls"]

    def test_parse_eml_extracts_body(self, sample_eml_b64):
        result = parse_eml_from_base64(sample_eml_b64)

        assert "Click here to win a prize!" in result["body_plain"]
        assert "evil.com/steal" in result["body_html"]

    def test_parse_eml_soc_fields(self, sample_eml_b64):
        result = parse_eml_from_base64(sample_eml_b64)

        assert result["reply_to"] == "phisher-reply@evil.com"
        assert result["return_path"] == "<bounce@evil.com>"
        assert result["x_originating_ip"] == "[192.168.1.100]"
        assert result["spf_result"] == "fail"
        assert result["dkim_result"] == "pass"
        assert result["dmarc_result"] == "fail"
        assert "mx.google.com" in result["authentication_results"]
        assert len(result["received_headers"]) >= 1
        assert "mail.evil.com" in result["received_headers"][0]


class TestParseMsgClose:
    """Verify extract_msg.Message.close() is always called to prevent resource leaks."""

    def _make_mock_msg(self):
        mock_msg = MagicMock()
        mock_msg.subject = "Test subject"
        mock_msg.sender = "sender@example.com"
        mock_msg.to = "to@example.com"
        mock_msg.cc = ""
        mock_msg.date = ""
        mock_msg.body = "plain body"
        mock_msg.htmlBody = None
        mock_msg.attachments = []
        return mock_msg

    def _fake_b64(self):
        return base64.b64encode(b"fake msg bytes").decode()

    def test_close_called_on_success(self):
        mock_msg = self._make_mock_msg()
        mock_lib = MagicMock()
        mock_lib.Message.return_value = mock_msg
        with patch.dict("sys.modules", {"extract_msg": mock_lib}):
            parse_msg_from_base64(self._fake_b64())
        mock_msg.close.assert_called_once()

    def test_close_called_even_when_parsing_raises(self):
        mock_msg = self._make_mock_msg()
        # Simulate a parsing error mid-way through result construction
        type(mock_msg).body = PropertyMock(side_effect=RuntimeError("unexpected parse error"))
        mock_lib = MagicMock()
        mock_lib.Message.return_value = mock_msg
        with patch.dict("sys.modules", {"extract_msg": mock_lib}):
            with pytest.raises(RuntimeError, match="unexpected parse error"):
                parse_msg_from_base64(self._fake_b64())
        mock_msg.close.assert_called_once()


def test_msg_uses_real_library_message_id_property_and_serializes_date():
    import json
    from datetime import UTC, datetime
    from email.message import EmailMessage
    from types import SimpleNamespace

    header = EmailMessage()
    header["Reply-To"] = "reply@example.com"
    msg = SimpleNamespace(
        subject="Subject",
        sender="sender@example.com",
        to="to@example.com",
        cc="",
        date=datetime(2026, 11, 10, tzinfo=UTC),
        messageId="<ActualProperty@example.com>",
        header=header,
        headerText=header.as_string(),
        body="Hello",
        htmlBody=None,
        attachments=[
            SimpleNamespace(longFilename="empty.txt", data=b"", mimetype="text/plain"),
            SimpleNamespace(longFilename="nested.msg", data=object()),
        ],
        close=MagicMock(),
    )
    library = MagicMock()
    library.Message.return_value = msg
    with patch.dict("sys.modules", {"extract_msg": library}):
        result = parse_msg_from_base64(base64.b64encode(b"msg").decode())
    assert result["message_id"] == "<ActualProperty@example.com>"
    assert result["reply_to"] == "reply@example.com"
    assert result["nested_attachments"][0]["sha256"] == hashlib.sha256(b"").hexdigest()
    assert result["nested_attachments"][1]["sha256"] is None
    assert result["nested_attachments"][1]["processing_error"]
    json.dumps(result)
    msg.close.assert_called_once()
