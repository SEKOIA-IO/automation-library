"""Utilities for parsing EML and MSG attachments."""

import base64
import codecs
import email
import email.policy
import hashlib
import logging
import re
from datetime import datetime
from email.errors import InvalidBase64CharactersDefect, InvalidBase64LengthDefect, InvalidBase64PaddingDefect
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r'https?://[^\s"<>\']+', re.IGNORECASE)


def _text_urls(text: str) -> list[str]:
    """Remove prose delimiters without stripping balanced URL brackets."""
    urls = []
    for url in _URL_RE.findall(text):
        excess = {
            closing: url.count(closing) - url.count(opening) for closing, opening in zip(")]}", "([{", strict=True)
        }
        end = len(url)
        while end:
            last = url[end - 1]
            if last in ".,;":
                end -= 1
            elif last in excess and excess[last] > 0:
                excess[last] -= 1
                end -= 1
            else:
                break
        urls.append(url[:end])
    return urls


class _HTMLURLs(HTMLParser):
    """Read link/resource attributes without treating markup as URL text."""

    URL_ATTRIBUTES = frozenset({"href", "src", "action", "formaction", "poster", "background", "cite", "originalsrc"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []
        self._hidden_text_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._hidden_text_depth += 1
        for name, value in attrs:
            if name in self.URL_ATTRIBUTES and value:
                # HTMLParser decodes attribute entities once; preserve encoded URL data.
                url = value.strip().replace("\r", "").replace("\n", "").replace("\t", "")
                self.urls.append(url.replace(" ", "%20"))

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._hidden_text_depth:
            self._hidden_text_depth -= 1

    def handle_data(self, data):
        if not self._hidden_text_depth:
            self.urls.extend(_text_urls(data))


def _extract_urls(body_html: str, body_plain: str) -> list[str]:
    """Extract and deduplicate HTTP(S) URLs from HTML and plain text."""
    parser = _HTMLURLs()
    parser.feed(body_html)
    parser.close()
    seen: set[str] = set()
    urls: list[str] = []
    for url in [*parser.urls, *_text_urls(body_plain)]:
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _extract_eml_parts(part: EmailMessage, result: dict[str, Any], bodies: dict[str, list[str]]) -> None:
    """Process attachments before bodies and do not descend into attached messages."""
    if (
        part.get_filename()
        or part.get_content_disposition() == "attachment"
        or part.get_content_type() == "message/rfc822"
        or (not part.is_multipart() and part.get_content_type() not in {"text/plain", "text/html"})
    ):
        raw = part.get_payload(decode=True)
        invalid_base64 = any(
            isinstance(defect, InvalidBase64CharactersDefect | InvalidBase64LengthDefect | InvalidBase64PaddingDefect)
            for defect in part.defects
        )
        if raw is None or invalid_base64:
            # The email parser exposes attached messages as objects. Serializing them
            # can refold headers and normalize line endings: it is not original evidence.
            result["nested_attachments"].append(
                {
                    "name": part.get_filename() or "",
                    "content_type": part.get_content_type(),
                    "size": None,
                    "sha256": None,
                    "processing_error": (
                        "Attachment base64 data is invalid"
                        if invalid_base64
                        else "Attachment data is unavailable as original bytes"
                    ),
                }
            )
            return
        raw = raw if isinstance(raw, bytes) else b""
        result["nested_attachments"].append(
            {
                "name": part.get_filename() or "",
                "content_type": part.get_content_type(),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        disposition = part.get_content_disposition()
        if part.get("Content-ID") or disposition:
            result["nested_attachments"][-1].update(
                content_id=str(part.get("Content-ID", "")),
                content_disposition=disposition or "",
                is_inline=disposition == "inline" or (disposition is None and bool(part.get("Content-ID"))),
            )
    elif part.is_multipart():
        for child in part.iter_parts():
            _extract_eml_parts(cast(EmailMessage, child), result, bodies)
    else:
        body_key = {"text/plain": "body_plain", "text/html": "body_html"}.get(part.get_content_type())
        if body_key:
            try:
                payload = part.get_content(errors="strict")
            except UnicodeError:
                payload = part.get_content(errors="replace")
                result.setdefault("processing_errors", []).append(
                    "Email body charset decoding required replacement characters"
                )
            except LookupError:
                raw_body = cast(bytes, part.get_payload(decode=True) or b"")
                payload = raw_body.decode("utf-8", errors="replace")
                result.setdefault("processing_errors", []).append(
                    "Email body charset is unknown; recovered text using UTF-8"
                )
            if isinstance(payload, str):
                bodies[body_key].append(payload)


def _header_evidence(message: email.message.Message) -> dict[str, Any]:
    """Preserve ordered, decoded header values and a case-insensitive multivalue lookup."""
    headers = [{"name": name, "value": str(value)} for name, value in message.items()]
    lookup: dict[str, list[str]] = {}
    for header in headers:
        lookup.setdefault(header["name"].lower(), []).append(header["value"])
    authentication = str(message.get("Authentication-Results", ""))
    auth = _parse_authentication_results(authentication)
    return {
        "headers": headers,
        "headers_map": lookup,
        "headers_available": bool(headers),
        "received_headers": [str(value) for value in message.get_all("Received", [])],
        "reply_to": str(message.get("Reply-To", "")),
        "return_path": str(message.get("Return-Path", "")),
        "x_mailer": str(message.get("X-Mailer", "")),
        "x_originating_ip": str(message.get("X-Originating-IP", "")),
        "authentication_results": authentication,
        "spf_result": auth.get("spf", ""),
        "dkim_result": auth.get("dkim", ""),
        "dmarc_result": auth.get("dmarc", ""),
    }


def _parse_authentication_results(header_value: str) -> dict[str, str]:
    """Parse an Authentication-Results header into spf/dkim/dmarc results."""
    results: dict[str, str] = {}
    if not header_value:
        return results
    for proto in ("spf", "dkim", "dmarc"):
        match = re.search(rf"{proto}=(\w+)", header_value, re.IGNORECASE)
        if match:
            results[proto] = match.group(1).lower()
    return results


def parse_eml_from_base64(content_b64: str) -> dict[str, Any]:
    """Parse a base64-encoded .eml file and extract structured data."""
    raw_bytes = base64.b64decode(content_b64, validate=True)
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    result: dict[str, Any] = {
        "subject": msg.get("Subject", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "date": msg.get("Date", ""),
        "message_id": msg.get("Message-ID", ""),
        "content_type": msg.get_content_type(),
        "body_plain": "",
        "body_html": "",
        "urls": [],
        "nested_attachments": [],
    }
    result.update(_header_evidence(msg))
    bodies: dict[str, list[str]] = {"body_plain": [], "body_html": []}
    _extract_eml_parts(msg, result, bodies)
    for key, sections in bodies.items():
        result[key] = "\n".join(sections)

    # Extract URLs from both HTML and plain-text bodies
    result["urls"] = _extract_urls(result["body_html"], result["body_plain"])

    return result


def _msg_text(value: Any, default: str = "") -> str:
    """Remove MSG string terminators from metadata without changing evidence bytes."""
    return value.rstrip("\x00") if isinstance(value, str) else default


def _decode_html_strict(raw: bytes, encoding: str) -> str | None:
    try:
        return raw.decode(encoding)
    except UnicodeError:
        return None
    except LookupError:
        return None


def _decode_msg_html(raw: bytes | None, message: Any) -> tuple[str, str | None]:
    if not raw:
        return "", None
    # BOMs take precedence over declarations, including UTF-32 before UTF-16.
    for marker, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ):
        if raw.startswith(marker):
            try:
                return raw.decode(encoding), None
            except UnicodeError:
                return raw.decode(encoding, errors="replace"), "MSG HTML contains invalid encoded characters."
    # Some MSG HTML streams are UTF-16 without a BOM or an ASCII-readable meta tag.
    if raw.startswith((b"<\x00", b"\x00<")):
        encoding = "utf-16-le" if raw.startswith(b"<\x00") else "utf-16-be"
        try:
            return raw.decode(encoding), None
        except UnicodeError:
            return raw.decode(encoding, errors="replace"), "MSG HTML contains invalid encoded characters."
    encodings = []
    warning = None
    for tag in re.findall(rb"<meta\b[^>]*>", raw[:8192], re.IGNORECASE):
        if match := re.search(rb"""charset\s*=\s*["']?\s*([\w.:-]+)""", tag, re.IGNORECASE):
            encodings.append(match[1].decode("ascii"))
            break
    if encodings:
        decoded = _decode_html_strict(raw, encodings[0])
        if decoded is not None:
            return decoded, None
        else:
            warning = "MSG HTML encoding could not be decoded as declared; recovered content may be incomplete."
    get_property = getattr(message, "getPropertyVal", None)
    codepage = get_property("3FDE0003") if callable(get_property) else None
    if isinstance(codepage, int) and codepage > 0:
        encodings.append({65001: "utf-8", 1200: "utf-16-le", 1201: "utf-16-be"}.get(codepage, f"cp{codepage}"))
    fallback = getattr(message, "stringEncoding", None)
    if isinstance(fallback, str) and not fallback.lower().startswith("utf-16"):
        encodings.append(fallback)
    encodings.append("utf-8")
    for encoding in dict.fromkeys(encodings):
        decoded = _decode_html_strict(raw, encoding)
        if decoded is not None:
            return decoded, warning
        else:
            warning = "MSG HTML encoding could not be decoded as declared; recovered content may be incomplete."
    return raw.decode("utf-8", errors="replace"), warning


def parse_msg_from_base64(content_b64: str) -> dict[str, Any]:
    """Parse a base64-encoded .msg file and extract structured data."""
    try:
        import extract_msg
    except ImportError:
        logger.warning("extract-msg not installed, skipping MSG parsing")
        raise RuntimeError("extract-msg is required for MSG parsing")

    raw_bytes = base64.b64decode(content_b64, validate=True)
    msg = extract_msg.Message(raw_bytes)
    try:
        # extract-msg's .header can synthesize headers from MAPI properties. Only
        # expose the transport header stream as original header evidence.
        transport = _msg_text(getattr(msg, "headerText", None))
        transport = transport.removeprefix("Microsoft Mail Internet Headers Version 2.0").lstrip()
        headers = email.message_from_string(transport, policy=email.policy.default) if transport else EmailMessage()
        html, html_error = _decode_msg_html(msg.htmlBody, msg)
        message_id = _msg_text(msg.messageId)
        result: dict[str, Any] = {
            "subject": _msg_text(msg.subject),
            "from": _msg_text(msg.sender),
            "to": _msg_text(msg.to),
            "cc": _msg_text(msg.cc),
            "date": msg.date.isoformat() if isinstance(msg.date, datetime) else "",
            "message_id": message_id,
            "body_plain": msg.body or "",
            "body_html": html,
            "urls": [],
            "nested_attachments": [],
        }
        result.update(_header_evidence(headers))
        if html_error:
            result["processing_errors"] = [html_error]

        for att in msg.attachments:
            att_name = (
                _msg_text(getattr(att, "longFilename", None))
                or _msg_text(getattr(att, "shortFilename", None))
                or "unknown"
            )
            att_data = getattr(att, "data", None)
            if not isinstance(att_data, bytes):
                result["nested_attachments"].append(
                    {
                        "name": att_name,
                        "size": None,
                        "sha256": None,
                        "processing_error": "Attachment data is unavailable as original bytes",
                    }
                )
                continue
            result["nested_attachments"].append(
                {
                    "name": att_name,
                    "content_type": _msg_text(getattr(att, "mimetype", None)) or "application/octet-stream",
                    "size": len(att_data),
                    "sha256": hashlib.sha256(att_data).hexdigest(),
                }
            )

        # Extract URLs from both HTML and plain-text bodies
        result["urls"] = _extract_urls(result["body_html"], result["body_plain"])
    finally:
        msg.close()

    return result
