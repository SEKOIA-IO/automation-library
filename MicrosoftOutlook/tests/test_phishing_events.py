import json
from copy import deepcopy

from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE

from microsoft_outlook_modules.phishing_events import build_evidence_events


def report():
    return {
        "id": "report-id",
        "collection_mailbox": "reports@example.com",
        "event_type": "microsoft_graph_mail_phishing_report",
        "received_datetime": "2026-11-10T12:56:55Z",
        "processing_errors": [],
        "eml_parsed_data": [
            {
                "subject": 'A "quoted" subject',
                "from": '"Doe, Jane" <jane@example.com>',
                "to": '"Doe, John" <john@example.com>, other@example.com',
                "message_id": "<original@example.com>",
                "source_attachment_id": "attachment-1",
                "source_sha256": "a" * 64,
                "source_mail_id": "report-id",
                "urls": [
                    "https://nam01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fexample.com%2Fx%3Fa%3D1%26b%3D2",
                    "https://example.com/x?a=1&b=2",
                ],
                "nested_attachments": [{"name": 'quote"\\é.txt', "size": 143, "sha256": "b" * 64}],
            }
        ],
    }


def test_multiple_originals_are_isolated_and_retry_identifiers_are_stable():
    raw = report()
    second = deepcopy(raw["eml_parsed_data"][0])
    second.update(subject="Second", source_attachment_id="attachment-2", message_id="<second@example.com>")
    raw["eml_parsed_data"].append(second)
    events = [json.loads(event) for event in build_evidence_events(raw, scope="tenant")]
    assert len(events) == 2
    assert [event["reported_email_index"] for event in events] == [0, 1]
    assert all(event["reported_email_count"] == 2 and len(event["eml_parsed_data"]) == 1 for event in events)
    assert events[0]["eml_parsed_data"][0]["subject"] != events[1]["eml_parsed_data"][0]["subject"]
    assert events[0]["report_event_id"] != events[1]["report_event_id"]
    assert build_evidence_events(raw, scope="tenant") == build_evidence_events(raw, scope="tenant")
    assert build_evidence_events(raw, scope="other-tenant") != build_evidence_events(raw, scope="tenant")
    raw["eml_parsed_data"].reverse()
    reordered = [json.loads(event) for event in build_evidence_events(raw, scope="tenant")]
    assert reordered[0]["report_event_id"] == events[1]["report_event_id"]


def test_normalized_addresses_and_safe_links_preserve_raw_evidence():
    raw = report()
    before = deepcopy(raw)
    event = json.loads(build_evidence_events(raw, scope="tenant")[0])
    original = event["eml_parsed_data"][0]
    assert original["from_addresses"] == ["jane@example.com"]
    assert original["to_addresses"] == ["john@example.com", "other@example.com"]
    assert original["destination_urls"] == ["https://example.com/x?a=1&b=2"]
    assert original["attachment_files"][0]["file"]["name"] == 'quote"\\é.txt'
    assert raw == before


def test_safe_links_lookalikes_are_not_unwrapped():
    raw = report()
    urls = [
        "https://safelinks.protection.outlook.com.evil.example/?url=https%3A%2F%2Fexample.com",
        "https://x.safelinks.protection.outlook.com/?url=javascript%3Aalert(1)",
    ]
    raw["eml_parsed_data"][0]["urls"] = urls
    event = json.loads(build_evidence_events(raw, scope="tenant")[0])
    assert event["eml_parsed_data"][0]["destination_urls"] == urls


def test_no_originals_and_failed_or_partial_extractions_are_explicit():
    raw = report()
    raw["eml_parsed_data"] = []
    event = json.loads(build_evidence_events(raw, scope="tenant")[0])
    assert event["extraction_status"] == "no_embedded_email"
    assert event["reported_email_count"] == 0
    raw["processing_errors"] = [{"error": "Attachment unavailable", "attachment_id": "a"}]
    assert json.loads(build_evidence_events(raw, scope="tenant")[0])["extraction_status"] == "failed"
    raw["eml_parsed_data"] = report()["eml_parsed_data"]
    assert json.loads(build_evidence_events(raw, scope="tenant")[0])["extraction_status"] == "partial"


def test_nested_unavailable_attachment_marks_incomplete_evidence():
    raw = report()
    raw["eml_parsed_data"][0]["nested_attachments"] = [{"name": "nested.msg", "processing_error": "Unavailable bytes"}]
    event = json.loads(build_evidence_events(raw, scope="tenant")[0])
    assert event["extraction_status"] == "partial"
    assert event["processing_errors"][0]["attachment_name"] == "nested.msg"


def test_oversized_evidence_retains_source_references_and_fits_sdk_limit():
    raw = report()
    original = raw["eml_parsed_data"][0]
    original["body_plain"] = "x" * 260000
    event = json.loads(build_evidence_events(raw, scope="tenant")[0])
    assert event["content_truncated"] and event["extraction_status"] == "partial"
    assert event["eml_parsed_data"][0]["source_attachment_id"] == "attachment-1"
    original["received_headers"] = ["x" * 260000]
    encoded = build_evidence_events(raw, scope="tenant")[0]
    assert len(encoded.encode()) <= EVENT_BYTES_MAX_SIZE
    event = json.loads(encoded)
    assert event["eml_parsed_data"][0]["source_sha256"] == "a" * 64
    assert event["processing_errors"]


def test_message_date_requires_an_explicit_timezone():
    raw = report()
    original = raw["eml_parsed_data"][0]
    for date in ("invalid", "2026-11-10T12:56:30", "Tue, 10 Nov 2026 12:56:30 -0000"):
        original["date"] = date
        parsed = json.loads(build_evidence_events(raw, scope="tenant")[0])["eml_parsed_data"][0]
        assert "origination_timestamp" not in parsed
        assert parsed["date"] == date
    original["date"] = "Tue, 10 Nov 2026 13:56:30 +0100"
    parsed = json.loads(build_evidence_events(raw, scope="tenant")[0])["eml_parsed_data"][0]
    assert parsed["origination_timestamp"] == "2026-11-10T13:56:30+01:00"
