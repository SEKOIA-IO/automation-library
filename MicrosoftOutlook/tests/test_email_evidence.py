"""Test MIME coverage, original header fidelity and MSG charset recovery."""

import base64
import hashlib
import json
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from microsoft_outlook_modules.attachments import collect_attachments
from microsoft_outlook_modules.eml_parser import parse_eml_from_base64, parse_msg_from_base64
from microsoft_outlook_modules.errors import describe_error
from microsoft_outlook_modules.phishing_events import build_evidence_events


def parse_eml(message):
    return parse_eml_from_base64(base64.b64encode(message.as_bytes()).decode())


def fake_msg(html=None, transport=None, codepage=None, encoding=None):
    return SimpleNamespace(
        subject="Subject",
        sender="sender@example.org",
        to="recipient@example.org",
        cc="",
        messageId="<id@example.org>",
        date=None,
        body="",
        htmlBody=html,
        attachments=[],
        headerText=transport,
        stringEncoding=encoding,
        getPropertyVal=Mock(return_value=codepage),
        close=Mock(),
    )


def parse_msg(message):
    library = Mock()
    library.Message.return_value = message
    with patch.dict("sys.modules", {"extract_msg": library}):
        result = parse_msg_from_base64(base64.b64encode(b"synthetic MSG").decode())
    message.close.assert_called_once()
    return result


@pytest.mark.parametrize("cte", ["base64", "quoted-printable", "8bit"])
def test_unnamed_inline_image_preserves_bytes_and_cid(cte):
    message = EmailMessage()
    message.set_content("Body")
    payload = b"inline image\x00\xff"
    message.add_related(payload, maintype="image", subtype="png", cid="<logo>", disposition="inline", cte=cte)
    result = parse_eml(message)
    image = result["nested_attachments"][0]
    assert image["name"] == ""
    assert image["content_id"] == "<logo>" and image["is_inline"]
    assert image["content_disposition"] == "inline"
    assert image["sha256"] == hashlib.sha256(payload).hexdigest()
    assert image["size"] == len(payload)
    assert result["body_plain"].strip() == "Body"


@pytest.mark.parametrize("subtype,key", [("plain", "body_plain"), ("html", "body_html")])
def test_multiple_body_sections_keep_all_links_and_exclude_attached_text(subtype, key):
    message = EmailMessage()
    message.make_mixed()
    for url in ["https://first.example/", "https://second.example/"]:
        part = EmailMessage()
        part.set_content(f'<a href="{url}">Link</a>' if subtype == "html" else url, subtype=subtype)
        message.attach(part)
    message.add_attachment(b"https://attachment.example/", maintype="text", subtype=subtype, filename="note.txt")
    result = parse_eml(message)
    assert "https://first.example/" in result[key] and "https://second.example/" in result[key]
    assert result["urls"] == ["https://first.example/", "https://second.example/"]


@pytest.mark.parametrize(
    "disposition,cid,expected_inline",
    [
        ("attachment", "<document>", False),
        ("attachment", None, False),
        ("inline", "<logo>", True),
        ("inline", None, True),
        (None, "<logo>", True),
    ],
)
def test_explicit_attachment_disposition_takes_precedence_over_cid(disposition, cid, expected_inline):
    message = EmailMessage()
    message.set_content("Body")
    part = EmailMessage()
    part.set_content(b"evidence bytes", maintype="application", subtype="octet-stream")
    if disposition:
        part["Content-Disposition"] = disposition
    if cid:
        part["Content-ID"] = cid
    message.make_mixed()
    message.attach(part)
    attachment = parse_eml(message)["nested_attachments"][0]
    assert attachment["is_inline"] is expected_inline
    assert attachment["content_disposition"] == (disposition or "")
    assert attachment["content_id"] == (cid or "")
    assert attachment["size"] == len(b"evidence bytes")
    assert attachment["sha256"] == hashlib.sha256(b"evidence bytes").hexdigest()


def test_multipart_alternative_preserves_both_representations():
    message = EmailMessage()
    message.set_content("Plain https://plain.example/")
    message.add_alternative('<a href="https://html.example/">HTML</a>', subtype="html")
    result = parse_eml(message)
    assert result["body_plain"].startswith("Plain")
    assert result["body_html"].startswith("<a")
    assert set(result["urls"]) == {"https://html.example/", "https://plain.example/"}


@pytest.mark.parametrize("kind", ["eml", "msg"])
def test_all_transport_headers_preserve_order_duplicates_and_common_fields(kind):
    transport = (
        "Received: newest hop\r\nReceived: oldest hop\r\n"
        "X-Custom: first\r\nx-custom: second\r\n"
        "Return-Path: <bounce@example.org>\r\nReply-To: reply@example.org\r\n"
        "Authentication-Results: mx.example; spf=pass; dkim=fail; dmarc=pass\r\n"
        "Authentication-Results: older.example; spf=fail\r\n"
    )
    if kind == "eml":
        result = parse_eml_from_base64(base64.b64encode((transport + "\r\nBody").encode()).decode())
    else:
        result = parse_msg(fake_msg(transport=transport))
    assert result["headers_available"]
    assert result["headers_map"]["x-custom"] == ["first", "second"]
    assert [header["name"] for header in result["headers"]][:2] == ["Received", "Received"]
    assert result["received_headers"] == ["newest hop", "oldest hop"]
    assert len(result["headers_map"]["authentication-results"]) == 2
    assert result["spf_result"] == "pass" and result["dkim_result"] == "fail"
    assert result["return_path"] == "<bounce@example.org>" and result["reply_to"] == "reply@example.org"
    json.dumps(result)


def test_missing_msg_transport_headers_are_not_synthesized():
    message = fake_msg()
    message.header = EmailMessage()
    message.header["Received"] = "generated, not original"
    result = parse_msg(message)
    assert not result["headers_available"] and result["headers"] == [] and result["headers_map"] == {}
    assert result["received_headers"] == [] and result["authentication_results"] == ""
    assert result["from"] == "sender@example.org"


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252", "utf-16", "utf-32", "utf-16-le", "utf-16-be"])
def test_msg_html_respects_bom_or_meta_charset(encoding):
    charset = "windows-1252" if encoding == "cp1252" else encoding
    html = f'<meta charset="{charset}"><a href="https://example.org/café">café</a>'
    result = parse_msg(fake_msg(html=html.encode(encoding)))
    assert "café" in result["body_html"] and "\ufffd" not in result["body_html"]
    assert result["urls"] == ["https://example.org/café"]
    assert not result.get("processing_errors")


def test_declared_html_charset_does_not_require_msg_codepage_properties():
    message = fake_msg(html=b'<meta charset="utf-8">text')
    message.getPropertyVal.side_effect = ValueError("unavailable codepage")
    assert parse_msg(message)["body_html"].endswith("text")
    message.getPropertyVal.assert_not_called()


@pytest.mark.parametrize("codepage,encoding", [(1252, None), (None, "cp1252")])
def test_msg_html_codepage_fallback(codepage, encoding):
    html = '<a href="https://example.org/café">café</a>'
    result = parse_msg(fake_msg(html=html.encode("cp1252"), codepage=codepage, encoding=encoding))
    assert result["urls"] == ["https://example.org/café"]
    assert not result.get("processing_errors")


@pytest.mark.parametrize("payload", [b'<meta charset="invalid-charset">text', b"invalid \xff text", b"\xff\xfe\x00"])
def test_unknown_or_lossy_msg_encoding_is_explicit_partial_evidence(payload):
    message = fake_msg(html=payload)
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "original.msg"}]
    graph.attachment_bytes.return_value = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    library = Mock()
    library.Message.return_value = message
    with patch.dict("sys.modules", {"extract_msg": library}):
        _, parsed, errors = collect_attachments(graph, "u", "r", embedded_only=True)
    assert errors and parsed
    event = json.loads(
        build_evidence_events({"id": "r", "eml_parsed_data": parsed, "processing_errors": errors}, scope="t")[0]
    )
    assert event["extraction_status"] == "partial"


def test_interrupted_write_requests_are_uncertain_and_not_automatically_retryable():
    from requests.exceptions import ChunkedEncodingError

    error = describe_error(ChunkedEncodingError(), may_modify=True)
    assert error["outcome_unknown"] and not error["retryable"]


@pytest.mark.parametrize(
    "headers,payload,expected_body,invalid_attachment",
    [
        (
            b'Content-Type: application/octet-stream\r\nContent-Disposition: attachment; filename="bad.bin"\r\n'
            b"Content-Transfer-Encoding: base64",
            b"A",
            None,
            True,
        ),
        (
            b"Content-Type: text/plain; charset=utf-8",
            b"https://example.org/caf\xe9",
            "https://example.org/caf\ufffd",
            False,
        ),
        (b"Content-Type: text/html; charset=utf-8", b"<p>caf\xe9</p>", "<p>caf\ufffd</p>", False),
        (b"Content-Type: text/plain; charset=unknown-charset", b"hello", "hello", False),
    ],
)
def test_damaged_eml_evidence_is_partial(headers, payload, expected_body, invalid_attachment):
    raw = b"Subject: Damaged evidence\r\nMIME-Version: 1.0\r\n" + headers + b"\r\n\r\n" + payload
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "original.eml", "contentType": "message/rfc822"}]
    graph.attachment_bytes.return_value = raw
    _, parsed, errors = collect_attachments(graph, "u", "r", embedded_only=True)
    assert len(parsed) == 1
    if invalid_attachment:
        attachment = parsed[0]["nested_attachments"][0]
        assert attachment["size"] is None
        assert attachment["sha256"] is None
        assert "base64" in attachment["processing_error"]
    else:
        assert expected_body in (parsed[0]["body_plain"], parsed[0]["body_html"])
        assert parsed[0]["processing_errors"]
        assert errors
    event = json.loads(
        build_evidence_events({"id": "r", "eml_parsed_data": parsed, "processing_errors": errors}, scope="t")[0]
    )
    assert event["extraction_status"] == "partial"
