"""Markdown comment for an alert or a case, built from a scan summary.

The URLs in the summary come from attackers, so every value is neutralised for Markdown before it is written.
"""

import re
from typing import Any

EMPTY = "—"
NEWLINES = re.compile(r"\r\n|\r|\n")
MARKDOWN_SPECIALS = re.compile(r"([\\|`\[\]<>])")
# Characters that would end or break a link destination.
DESTINATION_ESCAPES = {ord(char): f"%{ord(char):02X}" for char in " ()<>\\\r\n\t"}


def _text(value: Any) -> str:
    """A value outside a code span: Markdown specials are escaped with a backslash, line breaks become spaces."""
    text = NEWLINES.sub(" ", str(value)) if value is not None else ""
    return MARKDOWN_SPECIALS.sub(r"\\\1", text) or EMPTY


def _code(value: Any) -> str:
    """A value in a code span: backtick and pipe are percent-encoded so the value cannot leave the span."""
    text = NEWLINES.sub("", str(value)) if value is not None else ""
    text = text.replace("`", "%60").replace("|", "%7C")
    return f"`{text}`" if text else EMPTY


def _destination(url: str) -> str:
    return url.translate(DESTINATION_ESCAPES)


def _verdict(malicious: Any) -> str:
    if malicious is True:
        return "**MALICIOUS**"
    if malicious is False:
        return "**not malicious**"
    return "**unknown**"


def build_comment(summary: dict[str, Any]) -> str:
    """Ready-to-post Markdown for the scan summary."""
    verdict = summary["verdict"]
    page = summary["page"]

    asn = " ".join(str(part) for part in (page["asn"], page["asn_name"]) if part)
    rows = [
        ("Final URL", _code(page["url"])),
        ("IP / ASN / country", f"{_text(page['ip'])} / {_text(asn)} / {_text(page['country'])}"),
        ("Page title", _text(page["title"])),
        (
            "Categories / brands",
            f"{_text(', '.join(map(str, verdict['categories'])))} / {_text(', '.join(map(str, verdict['brands'])))}",
        ),
        ("Engines", f"{_text(verdict['engines_malicious'])}/{_text(verdict['engines_total'])}"),
        ("Scan time", _text(summary["scan_time"])),
    ]
    blocks = [
        f"**urlscan.io scan** of {_code(summary['submitted_url'])} — verdict: {_verdict(verdict['malicious'])}"
        f" (score {_text(verdict['score'])})",
        "\n".join(["| | |", "| --- | --- |", *(f"| {name} | {value} |" for name, value in rows)]),
    ]

    links = [
        f"[{label}]({_destination(url)})"
        for label, url in (
            ("urlscan.io report", summary["report_url"]),
            ("Screenshot", summary["screenshot_url"]),
            ("DOM", summary["dom_url"]),
        )
        if url is not None
    ]
    if links:
        blocks.append(" · ".join(links))

    if summary["screenshot_url"] is not None:
        blocks.append(f"![Screenshot of the scanned page]({_destination(summary['screenshot_url'])})")
    else:
        blocks.append("Screenshot: not stored by urlscan.io")
    return "\n\n".join(blocks)
