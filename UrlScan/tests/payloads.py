BASE = "https://urlscan.io"
SCAN_ID = "01a19eb3-3b83-739b-87b9-48907fc34bae"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
FILE = {
    "filename": "a.zip",
    "sha256": "ab" * 32,
    "filesize": 10,
    "mimeType": "application/zip",
    "mimeDescription": "Zip archive",
    "url": "https://example.com/a.zip",
    "state": "completed",
}


def submission_payload(**overrides) -> dict:
    return {
        "message": "Submission successful",
        "uuid": SCAN_ID,
        "result": f"{BASE}/result/{SCAN_ID}/",
        "api": f"{BASE}/api/v1/result/{SCAN_ID}/",
        "visibility": "private",
        "options": {},
        "url": "https://example.com/",
        "country": "fr",
    } | overrides


def result_payload() -> dict:
    return {
        "task": {
            "uuid": SCAN_ID,
            "url": "https://example.com/",
            "visibility": "private",
            "time": "2026-11-02T23:58:34.078Z",
            "tags": ["sekoia"],
            "reportURL": f"{BASE}/result/{SCAN_ID}/",
            "screenshotURL": f"{BASE}/screenshots/{SCAN_ID}.png",
            "domURL": f"{BASE}/dom/{SCAN_ID}/",
        },
        "verdicts": {
            "overall": {"malicious": False, "score": 0, "categories": [], "brands": [], "tags": []},
            "engines": {"maliciousTotal": 0, "enginesTotal": 0},
            "community": {"votesMalicious": 0},
        },
        "page": {
            "url": "https://example.com/",
            "domain": "example.com",
            "apexDomain": "example.com",
            "ip": "203.0.113.10",
            "ptr": "host.example.net",
            "asn": "AS64500",
            "asnname": "EXAMPLE-AS, US",
            "country": "US",
            "city": "Paris",
            "server": "ECS",
            "title": "Example Domain",
            "status": "200",
            "mimeType": "text/html",
            "redirected": "off-domain",
            "domainAgeDays": 11000,
            "tlsIssuer": "Example CA",
            "tlsValidDays": 90,
        },
        "visible": {"brandname": "Example"},
        "lists": {"domains": ["example.com"], "ips": ["203.0.113.10"], "countries": ["US"], "asns": ["64500"]},
        "stats": {"malicious": 0, "securePercentage": 100},
        "data": {"requests": [{}, {}]},
        "meta": {"processors": {"download": {"data": [FILE]}}},
    }


def search_hit(index: int) -> dict:
    scan_id = f"0000000{index}-0000-0000-0000-000000000000"
    return {
        "_id": scan_id,
        "sort": [1793663105646 - index, f"id-{index}"],
        "task": {"time": "2026-11-02T23:58:34.078Z", "url": "https://example.com/", "visibility": "public"},
        "page": {
            "url": "https://example.com/",
            "domain": "example.com",
            "ip": "203.0.113.10",
            "asn": "AS64500",
            "asnname": "EXAMPLE-AS, US",
            "country": "US",
            "title": "Example Domain",
            "status": "200",
        },
        "verdicts": {"malicious": False, "score": 0},
        "result": f"{BASE}/api/v1/result/{scan_id}/",
        "screenshot": f"{BASE}/screenshots/{scan_id}.png",
        "files": [FILE],
    }


def search_payload(count: int = 2) -> dict:
    return {"total": 5, "took": 3, "has_more": False, "results": [search_hit(index) for index in range(count)]}
