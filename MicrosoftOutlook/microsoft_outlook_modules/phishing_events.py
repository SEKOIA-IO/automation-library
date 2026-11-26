"""Versioned evidence events: one reported original per event, linked to its report."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE


def _addresses(value: str) -> list[str]:
    return list(dict.fromkeys(address for _, address in getaddresses([value]) if address))


def _destinations(urls: list[str]) -> list[str]:
    """Decode recognized Microsoft Safe Links without following any remote URL."""
    result = []
    seen: set[str] = set()
    for url in urls:
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            if host.endswith(".safelinks.protection.outlook.com"):
                candidate = parse_qs(parsed.query).get("url", [url])[0]
                target = urlsplit(candidate)
                if target.scheme.lower() in {"http", "https"} and target.hostname:
                    url = candidate
        except ValueError:
            continue
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _prepare_original(original: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(original)
    for field in ("from", "to", "cc", "reply_to"):
        result[f"{field}_addresses"] = _addresses(str(result.get(field) or ""))
    result["sender_addresses"] = _addresses(str(result.get("return_path") or ""))
    date = str(result.get("date") or "")
    if date:
        try:
            try:
                parsed_date = datetime.fromisoformat(date)
            except ValueError:
                parsed_date = parsedate_to_datetime(date)
            if parsed_date.tzinfo is not None:
                result["origination_timestamp"] = parsed_date.isoformat()
        except ValueError:
            pass  # Keep the original date, without inventing a timezone or timestamp.
        except TypeError:
            pass
        except OverflowError:
            pass
    result["destination_urls"] = _destinations(result.get("urls") or [])
    # Keep the native list structure: filenames and addresses must never be interpolated into JSON.
    result["attachment_files"] = []
    for attachment in result.get("nested_attachments") or []:
        file = {
            target: attachment[source]
            for source, target in (("name", "name"), ("content_type", "mime_type"), ("size", "size"))
            if attachment.get(source) is not None
        }
        if attachment.get("sha256"):
            file["hash"] = {"sha256": attachment["sha256"]}
        result["attachment_files"].append({"file": file})
    return result


def build_evidence_events(report: dict[str, Any], *, scope: str) -> list[str]:
    """Keep report IDs distinct from original Internet IDs and retry-stable event IDs.

    A report with no extracted originals still produces one explicit status event.
    All originals are delivered in the same acknowledged batch before checkpointing.
    """
    originals = report.get("eml_parsed_data") or []
    errors = report.get("processing_errors") or []
    events = []
    for index, original in enumerate(originals or [None]):
        event = {key: value for key, value in report.items() if key != "eml_parsed_data"}
        nested_errors = (
            []
            if original is None
            else [
                {"attachment_name": item.get("name", ""), "error": item["processing_error"]}
                for item in original.get("nested_attachments", [])
                if item.get("processing_error")
            ]
        )
        event["processing_errors"] = [*errors, *nested_errors]
        status = "partial" if event["processing_errors"] else "complete"
        if original is None:
            status = "failed" if errors else "no_embedded_email"
        source_id = original.get("source_attachment_id") if original else None
        identity = [
            scope,
            report.get("collection_mailbox"),
            report["id"],
            source_id,
            index if original and not source_id else None,
        ]
        event.update(
            schema_version=2,
            report_event_id=hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest(),
            reported_email_count=len(originals),
            extraction_status=status,
            content_truncated=False,
            eml_parsed_data=[_prepare_original(original)] if original is not None else [],
        )
        if original is not None:
            event["reported_email_index"] = index
        encoded = json.dumps(event)
        if len(encoded.encode()) > EVENT_BYTES_MAX_SIZE:
            # Retain independently useful evidence before falling back to reference-only metadata.
            event.pop("body_content", None)
            event.pop("body_preview", None)
            for parsed in event["eml_parsed_data"]:
                parsed.pop("body_html", None)
                parsed.pop("body_plain", None)
            event["content_truncated"] = True
            event["extraction_status"] = "partial"
            event["processing_errors"].append(
                {"error": "Evidence exceeds intake size limit; retrieve source via Graph"}
            )
            encoded = json.dumps(event)
            if len(encoded.encode()) > EVENT_BYTES_MAX_SIZE:
                keep = (
                    "event_type",
                    "schema_version",
                    "report_event_id",
                    "id",
                    "received_datetime",
                    "collection_mailbox",
                    "reported_email_count",
                    "reported_email_index",
                )
                event = {key: event[key] for key in keep if key in event}
                source = (
                    {}
                    if original is None
                    else {
                        key: original[key]
                        for key in (
                            "source_mail_id",
                            "source_attachment_id",
                            "source_sha256",
                            "source_graph_attachment_type",
                            "source_detected_format",
                        )
                        if key in original
                    }
                )
                event.update(
                    eml_parsed_data=[source] if source else [],
                    content_truncated=True,
                    extraction_status="partial",
                    processing_errors=[{"error": "Evidence exceeds intake size limit; retrieve source via Graph"}],
                )
                encoded = json.dumps(event)
        events.append(encoded)
    return events
