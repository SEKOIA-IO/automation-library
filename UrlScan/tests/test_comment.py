from typing import Any

from tests.payloads import BASE, SCAN_ID, result_payload
from urlscan_modules.comment import build_comment
from urlscan_modules.formatters import build_scan_summary


def summary_with(**overrides: Any) -> dict[str, Any]:
    """Scan summary of the sample result; "verdict" and "page" overrides are merged into the sections."""
    summary = build_scan_summary(result_payload(), BASE)
    for section in ("verdict", "page"):
        summary[section] |= overrides.pop(section, {})
    return summary | overrides


def test_comment_not_malicious():
    comment = build_comment(summary_with())

    assert comment == (
        "**urlscan.io scan** of `https://example.com/` — verdict: **not malicious** (score 0)\n"
        "\n"
        "| | |\n"
        "| --- | --- |\n"
        "| Final URL | `https://example.com/` |\n"
        "| IP / ASN / country | 203.0.113.10 / AS64500 EXAMPLE-AS, US / US |\n"
        "| Page title | Example Domain |\n"
        "| Categories / brands | — / — |\n"
        "| Engines | 0/0 |\n"
        "| Scan time | 2026-11-02T23:58:34.078Z |\n"
        "\n"
        f"[urlscan.io report]({BASE}/result/{SCAN_ID}/) · [Screenshot]({BASE}/screenshots/{SCAN_ID}.png)"
        f" · [DOM]({BASE}/dom/{SCAN_ID}/)\n"
        "\n"
        f"![Screenshot of the scanned page]({BASE}/screenshots/{SCAN_ID}.png)"
    )


def test_comment_malicious():
    comment = build_comment(
        summary_with(verdict={"malicious": True, "score": 100, "categories": ["phishing"], "brands": ["paypal"]})
    )

    assert comment.splitlines()[0].endswith("— verdict: **MALICIOUS** (score 100)")
    assert "| Categories / brands | phishing / paypal |" in comment.splitlines()


def test_comment_without_screenshot_and_dom():
    comment = build_comment(summary_with(screenshot_url=None, dom_url=None))

    lines = comment.splitlines()
    assert lines[-3] == f"[urlscan.io report](https://urlscan.io/result/{SCAN_ID}/)"
    assert lines[-1] == "Screenshot: not stored by urlscan.io"
    assert "![" not in comment


def test_comment_escapes_page_values():
    comment = build_comment(summary_with(page={"title": "a|b `c` [x](http://evil) <img>\nnext"}))

    assert "| Page title | a\\|b \\`c\\` \\[x\\](http://evil) \\<img\\> next |" in comment.splitlines()


def test_comment_keeps_urls_inert():
    evil = "https://evil.example/`](https://x) |\nb"
    inert = "https://evil.example/%60](https://x) %7Cb"

    comment = build_comment(summary_with(submitted_url=evil, page={"url": evil}))

    lines = comment.splitlines()
    assert lines[0].startswith(f"**urlscan.io scan** of `{inert}` —")
    assert f"| Final URL | `{inert}` |" in lines
