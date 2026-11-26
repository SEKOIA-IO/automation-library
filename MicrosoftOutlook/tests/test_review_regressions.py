"""Protect evidence fidelity, partial outcomes and bounded URL processing."""

import base64
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from microsoft_outlook_modules.action_extract_email import ExtractEmailAction
from microsoft_outlook_modules.attachments import collect_attachments
from microsoft_outlook_modules.eml_parser import _text_urls, parse_eml_from_base64
from microsoft_outlook_modules.phishing_events import _destinations, build_evidence_events


@pytest.mark.parametrize("content_type", ["application/octet-stream", ""])
def test_generic_binary_is_not_a_failed_email(content_type):
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "file.bin", "contentType": content_type}]
    graph.attachment_bytes.return_value = b"\x00\x01\xff"
    attachments, originals, errors = collect_attachments(graph, "u", "m", embedded_only=True)
    assert not originals and not errors
    assert attachments[0]["detected_format"] == "unknown"


@pytest.mark.parametrize("content_type", ["application/octet-stream", ""])
def test_generic_email_bytes_are_still_discovered(content_type, sample_eml_b64):
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "contentType": content_type}]
    graph.attachment_bytes.return_value = base64.b64decode(sample_eml_b64)
    _, originals, errors = collect_attachments(graph, "u", "m", embedded_only=True)
    assert not errors
    assert originals[0]["message_id"] == "<original@evil.com>"


def test_nested_mime_does_not_publish_reconstructed_hash():
    inner = b"From: sender@example.org\r\nSubject: nested\r\n\r\nbody\r\n"
    outer = (
        b"From: outer@example.org\r\nMIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=b\r\n\r\n--b\r\n"
        b"Content-Type: message/rfc822\r\nContent-Disposition: attachment; filename=nested.eml\r\n\r\n"
        + inner
        + b"\r\n--b--\r\n"
    )
    parsed = parse_eml_from_base64(base64.b64encode(outer).decode())
    nested = parsed["nested_attachments"][0]
    assert nested["size"] is None and nested["sha256"] is None
    assert nested["processing_error"]
    import json

    event = json.loads(build_evidence_events({"id": "r", "eml_parsed_data": [parsed]}, scope="tenant")[0])
    assert event["extraction_status"] == "partial"
    assert "hash" not in event["eml_parsed_data"][0]["attachment_files"][0]["file"]


def test_msg_nested_failure_produces_partial_action(configured_action):
    action = configured_action(ExtractEmailAction)
    action.__dict__["client"] = Mock()
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "original.msg"}]
    graph.attachment_bytes.return_value = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    message = SimpleNamespace(
        header=None,
        subject="Recovered original",
        sender="",
        to="",
        cc="",
        messageId="",
        date=None,
        body="",
        htmlBody=None,
        attachments=[SimpleNamespace(longFilename="nested.msg", data=object())],
        close=Mock(),
    )
    library = Mock()
    library.Message.return_value = message
    with (
        patch.dict("sys.modules", {"extract_msg": library}),
        patch("microsoft_outlook_modules.action_extract_email.MailGraph", return_value=graph),
    ):
        result = action.run({"user": "u", "message_id": "m"})
    assert result["outcome"] == "partial"
    assert result["parsed_emails"][0]["subject"] == "Recovered original"
    assert result["error_details"][0]["attachment_name"] == "nested.msg"
    assert result["error_details"][0]["attachment_id"] == "a"
    assert action.error_message
    message.close.assert_called_once()


def test_url_trimming_counts_once_and_slices_once():
    class ObservedURL(str):
        counts = 0
        slices = 0

        def count(self, *args):
            self.counts += 1
            return super().count(*args)

        def __getitem__(self, key):
            if isinstance(key, slice):
                self.slices += 1
            return super().__getitem__(key)

    url = ObservedURL("https://example.org/(balanced)" + ")" * 40000 + ".,;")
    with patch("microsoft_outlook_modules.eml_parser._URL_RE") as expression:
        expression.findall.return_value = [url]
        assert _text_urls("input") == ["https://example.org/(balanced)"]
    assert url.counts == 6
    assert url.slices == 1


def test_destination_deduplication_uses_bounded_membership_and_preserves_order():
    class ObservedURL(str):
        comparisons = 0
        __hash__ = str.__hash__

        def __eq__(self, other):
            type(self).comparisons += 1
            return super().__eq__(other)

    urls = [ObservedURL(f"https://example.org/{i}") for i in range(1000)]
    result = _destinations([*urls, *urls])
    assert ObservedURL.comparisons < 10000
    assert list(map(str, result)) == list(map(str, urls))


def test_safe_link_and_original_destination_are_deduplicated_in_first_seen_order():
    assert _destinations(
        [
            "https://a.safelinks.protection.outlook.com/?url=https%3A%2F%2Fexample.org%2F",
            "https://example.org/",
            "https://other.example/",
            "https://example.org/",
        ]
    ) == ["https://example.org/", "https://other.example/"]
