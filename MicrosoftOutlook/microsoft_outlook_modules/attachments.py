"""Shared attachment download, evidence metadata and embedded-message parsing."""

import base64
import hashlib
from email.parser import BytesHeaderParser
from typing import Any

from .eml_parser import parse_eml_from_base64, parse_msg_from_base64
from .errors import AttachmentError, describe_error
from .graph import MailGraph


def is_embedded_message(attachment: dict[str, Any]) -> bool:
    name = (attachment.get("name") or "").lower()
    content_type = (attachment.get("contentType") or "").lower()
    return (
        name.endswith((".eml", ".msg"))
        or content_type in {"message/rfc822", "application/vnd.ms-outlook"}
        or attachment.get("@odata.type") == "#microsoft.graph.itemAttachment"
    )


def detect_email_format(raw: bytes) -> str:
    """Identify the parsing route from downloaded bytes, never from the filename.

    The MSG signature identifies an OLE container; successful parsing is still required
    to establish that it contains a readable Outlook message.
    """
    if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "msg"
    headers = BytesHeaderParser().parsebytes(raw)
    if any(headers.get(field) for field in ("From", "To", "Subject", "Date", "Message-ID")):
        return "eml"
    return "unknown"


def parse_embedded(raw: bytes, *, detected_format: str | None = None) -> dict[str, Any]:
    detected_format = detected_format or detect_email_format(raw)
    if detected_format == "unknown":
        raise AttachmentError("Attachment does not contain recognizable email headers")
    content = base64.b64encode(raw).decode("ascii")
    if detected_format == "msg":
        return parse_msg_from_base64(content)
    return parse_eml_from_base64(content)


def collect_attachments(
    graph: MailGraph,
    user: str,
    message_id: str,
    *,
    include_content: bool = False,
    embedded_only: bool = False,
    parse_messages: bool = True,
    raise_retryable: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    attachments = []
    parsed_emails = []
    errors = []
    for item in graph.attachments(user, message_id):
        info = {
            "user": user,
            "message_id": message_id,
            "attachment_id": item["id"],
            "name": item.get("name") or "",
            "content_type": item.get("contentType") or "",
            "graph_attachment_type": item.get("@odata.type") or "",
            "size": item.get("size") or 0,
        }
        try:
            explicit_email = is_embedded_message(item)
            probe_email = (item.get("contentType") or "").lower() in {"application/octet-stream", ""}
            if embedded_only and not explicit_email and not probe_email:
                attachments.append(info)
                continue
            raw = graph.attachment_bytes(user, message_id, item)
            info.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            info["detected_format"] = detect_email_format(raw)
            if include_content:
                info["base64_content"] = base64.b64encode(raw).decode("ascii")
            if parse_messages and (explicit_email or info["detected_format"] != "unknown"):
                parsed = parse_embedded(raw, detected_format=info["detected_format"])
                parsed.update(
                    source_mail_id=message_id,
                    source_attachment=item.get("name") or "",
                    source_attachment_id=item["id"],
                    source_sha256=info["sha256"],
                    source_graph_attachment_type=info["graph_attachment_type"],
                    source_detected_format=info["detected_format"],
                )
                parsed_emails.append(parsed)
                for warning in parsed.get("processing_errors", []):
                    detail = describe_error(AttachmentError(warning))
                    errors.append({"message_id": message_id, "attachment_id": item["id"], **detail})
        except Exception as exc:
            # Preserve the attachment reference and explicit failure, never silently claim complete analysis.
            detail = describe_error(exc)
            if raise_retryable and detail["retryable"]:
                # Do not checkpoint a report whose evidence can be recovered on a later poll.
                raise
            errors.append(
                {"message_id": message_id, "attachment_id": item["id"], "error": detail["message"], **detail}
            )
        attachments.append(info)
    return attachments, parsed_emails, errors
