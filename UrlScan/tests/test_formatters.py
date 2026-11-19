import pytest

from tests.payloads import BASE, SCAN_ID, result_payload, submission_payload
from urlscan_modules.comment import build_comment
from urlscan_modules.formatters import (
    blacklisted_summary,
    build_scan_summary,
    empty_scan_summary,
    submitted_summary,
)

TOP_LEVEL_KEYS = [
    "uuid",
    "status",
    "submitted_url",
    "visibility",
    "scan_time",
    "tags",
    "verdict",
    "page",
    "brand",
    "contacted",
    "stats",
    "downloaded_files",
    "report_url",
    "result_api_url",
    "screenshot_available",
    "screenshot_url",
    "dom_available",
    "dom_url",
    "comment",
]
VERDICT_KEYS = [
    "malicious",
    "score",
    "categories",
    "brands",
    "tags",
    "engines_malicious",
    "engines_total",
    "community_votes_malicious",
]
PAGE_KEYS = [
    "url",
    "domain",
    "apex_domain",
    "ip",
    "ptr",
    "asn",
    "asn_name",
    "country",
    "city",
    "server",
    "title",
    "status",
    "mime_type",
    "redirected",
    "domain_age_days",
    "tls_issuer",
    "tls_valid_days",
]


def test_empty_scan_summary_shape():
    summary = empty_scan_summary()

    assert list(summary) == TOP_LEVEL_KEYS
    assert list(summary["verdict"]) == VERDICT_KEYS
    assert list(summary["page"]) == PAGE_KEYS
    assert list(summary["contacted"]) == ["domains", "ips", "countries", "asns"]
    assert list(summary["stats"]) == ["requests", "malicious", "secure_percentage"]
    assert summary["tags"] == []
    assert summary["contacted"] == {"domains": [], "ips": [], "countries": [], "asns": []}
    assert summary["downloaded_files"] == []
    assert summary["uuid"] is None


def test_empty_scan_summary_is_not_shared_between_calls():
    first = empty_scan_summary()
    first["tags"].append("x")
    first["contacted"]["ips"].append("1.1.1.1")

    assert empty_scan_summary()["tags"] == []
    assert empty_scan_summary()["contacted"]["ips"] == []


def test_build_scan_summary_maps_fields():
    summary = build_scan_summary(result_payload(), BASE)

    assert list(summary) == TOP_LEVEL_KEYS
    assert summary["status"] == "done"
    assert summary["uuid"] == SCAN_ID
    assert summary["submitted_url"] == "https://example.com/"
    assert summary["visibility"] == "private"
    assert summary["scan_time"] == "2026-11-02T23:58:34.078Z"
    assert summary["tags"] == ["sekoia"]
    assert summary["verdict"] == {
        "malicious": False,
        "score": 0,
        "categories": [],
        "brands": [],
        "tags": [],
        "engines_malicious": 0,
        "engines_total": 0,
        "community_votes_malicious": 0,
    }
    assert summary["page"]["apex_domain"] == "example.com"
    assert summary["page"]["asn_name"] == "EXAMPLE-AS, US"
    assert summary["page"]["mime_type"] == "text/html"
    assert summary["page"]["domain_age_days"] == 11000
    assert summary["page"]["tls_valid_days"] == 90
    assert summary["brand"] == "Example"
    assert summary["contacted"]["asns"] == ["64500"]
    assert summary["stats"] == {"requests": 2, "malicious": 0, "secure_percentage": 100}
    assert summary["downloaded_files"] == [
        {
            "filename": "a.zip",
            "sha256": "ab" * 32,
            "size": 10,
            "mime_type": "application/zip",
            "mime_description": "Zip archive",
            "url": "https://example.com/a.zip",
            "state": "completed",
        }
    ]
    assert summary["report_url"] == f"{BASE}/result/{SCAN_ID}/"
    assert summary["result_api_url"] == f"{BASE}/api/v1/result/{SCAN_ID}/"
    assert summary["screenshot_url"] == f"{BASE}/screenshots/{SCAN_ID}.png"
    assert summary["dom_url"] == f"{BASE}/dom/{SCAN_ID}/"
    assert summary["screenshot_available"] is None
    assert summary["dom_available"] is None
    assert summary["comment"] is None


def test_result_api_url_from_submission():
    custom = "https://urlscan.io/api/v1/result/custom/"

    summary = build_scan_summary(result_payload(), BASE, submission_payload(api=custom))

    assert summary["result_api_url"] == custom


def test_zero_requests_stay_zero():
    result = result_payload()
    result["data"]["requests"] = []

    assert build_scan_summary(result, BASE)["stats"]["requests"] == 0


@pytest.mark.parametrize(
    "result",
    [
        {"task": {"uuid": SCAN_ID}},
        {
            "task": {"uuid": SCAN_ID},
            "page": None,
            "verdicts": None,
            "lists": None,
            "stats": None,
            "data": None,
            "meta": None,
            "visible": None,
        },
    ],
)
def test_missing_sections_keep_the_shape(result):
    summary = build_scan_summary(result, BASE)

    assert list(summary) == list(empty_scan_summary())
    assert list(summary["page"]) == PAGE_KEYS
    assert list(summary["verdict"]) == VERDICT_KEYS
    assert summary["page"]["title"] is None
    assert summary["contacted"]["domains"] == []
    assert summary["stats"]["requests"] is None
    assert summary["downloaded_files"] == []

    lines = build_comment(summary).splitlines()
    assert lines[0] == "**urlscan.io scan** of — — verdict: **unknown** (score —)"
    assert "| Final URL | — |" in lines
    assert "| IP / ASN / country | — / — / — |" in lines
    assert "| Engines | —/— |" in lines
    assert lines[-1] == "Screenshot: not stored by urlscan.io"
    assert "](" not in "\n".join(lines)


def test_submitted_summary():
    submission = submission_payload()

    summary = submitted_summary(submission, BASE)

    expected = empty_scan_summary() | {
        "uuid": SCAN_ID,
        "status": "submitted",
        "submitted_url": "https://example.com/",
        "visibility": "private",
        "report_url": f"{BASE}/result/{SCAN_ID}/",
        "result_api_url": f"{BASE}/api/v1/result/{SCAN_ID}/",
    }
    assert summary == expected
    assert list(summary) == TOP_LEVEL_KEYS


def test_blacklisted_summary():
    summary = blacklisted_summary("https://bad.example/")

    assert summary == empty_scan_summary() | {"status": "blacklisted", "submitted_url": "https://bad.example/"}
