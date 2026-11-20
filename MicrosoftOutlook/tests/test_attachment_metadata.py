"""Prove that format metadata reflects bytes rather than a misleading filename."""

import base64
from unittest.mock import Mock, patch

from microsoft_outlook_modules.attachments import collect_attachments
from microsoft_outlook_modules.phishing_events import build_evidence_events


def test_graph_item_attachment_returning_mime_exposes_eml_format(sample_eml_b64):
    graph = Mock()
    graph.attachments.return_value = [
        {
            "id": "a",
            "name": "exported.msg",
            "contentType": "application/vnd.ms-outlook",
            "@odata.type": "#microsoft.graph.itemAttachment",
        }
    ]
    graph.attachment_bytes.return_value = base64.b64decode(sample_eml_b64)
    attachments, parsed, errors = collect_attachments(graph, "u", "m")
    assert not errors
    assert attachments[0]["name"] == "exported.msg"
    assert attachments[0]["content_type"] == "application/vnd.ms-outlook"
    assert attachments[0]["graph_attachment_type"] == "#microsoft.graph.itemAttachment"
    assert attachments[0]["detected_format"] == "eml"
    assert parsed[0]["source_detected_format"] == "eml"
    assert parsed[0]["source_graph_attachment_type"] == "#microsoft.graph.itemAttachment"


def test_ole_attachment_selects_msg_parser_and_records_graph_type():
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "message", "@odata.type": "#microsoft.graph.fileAttachment"}]
    graph.attachment_bytes.return_value = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1synthetic"
    with patch(
        "microsoft_outlook_modules.attachments.parse_msg_from_base64", return_value={"subject": "MSG"}
    ) as parse:
        attachments, parsed, errors = collect_attachments(graph, "u", "m")
    parse.assert_called_once()
    assert not errors
    assert attachments[0]["detected_format"] == parsed[0]["source_detected_format"] == "msg"
    assert parsed[0]["source_graph_attachment_type"] == "#microsoft.graph.fileAttachment"


def test_unrecognized_bytes_and_unknown_graph_type_are_not_guessed():
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "bad.msg"}]
    graph.attachment_bytes.return_value = b"not a recognizable email"
    attachments, parsed, errors = collect_attachments(graph, "u", "m")
    assert not parsed and errors
    assert attachments[0]["graph_attachment_type"] == ""
    assert attachments[0]["detected_format"] == "unknown"


def test_download_without_parsing_still_exposes_format(sample_eml_b64):
    graph = Mock()
    graph.attachments.return_value = [{"id": "a", "name": "message.eml"}]
    graph.attachment_bytes.return_value = base64.b64decode(sample_eml_b64)
    attachments, parsed, errors = collect_attachments(graph, "u", "m", parse_messages=False)
    assert not parsed and not errors
    assert attachments[0]["detected_format"] == "eml"


def test_format_metadata_survives_reference_only_size_fallback():
    import json

    report = {
        "id": "r",
        "collection_mailbox": "reports@example.org",
        "eml_parsed_data": [
            {
                "source_attachment_id": "a",
                "source_detected_format": "msg",
                "source_graph_attachment_type": "#microsoft.graph.fileAttachment",
                "received_headers": ["x" * 260000],
            }
        ],
    }
    event = json.loads(build_evidence_events(report, scope="tenant")[0])
    assert event["content_truncated"]
    assert event["eml_parsed_data"][0]["source_detected_format"] == "msg"
    assert event["eml_parsed_data"][0]["source_graph_attachment_type"] == "#microsoft.graph.fileAttachment"
