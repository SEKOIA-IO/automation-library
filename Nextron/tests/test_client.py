import json

import requests_mock

from thor_cloud_modules import client


def test_get_base_url_lite():
    assert client.get_base_url("thor_cloud_lite") == "https://thorcloud-lite.nextron-systems.com"


def test_get_base_url_cloud():
    assert client.get_base_url("thor_cloud") == "https://thorcloud.nextron-services.com"


def test_get_headers_uses_raw_api_key():
    """API key must be sent raw in Authorization (no 'Bearer' prefix)."""
    headers = client.get_headers("test-key-123")
    assert headers["Authorization"] == "test-key-123"
    assert "Bearer" not in headers["Authorization"]


def test_parse_campaigns():
    """Comma-separated textbox input -> clean UUID list; empty -> None (all campaigns)."""
    # empty / whitespace-only / None all mean "all campaigns"
    assert client.parse_campaigns(None) is None
    assert client.parse_campaigns("") is None
    assert client.parse_campaigns("   ") is None
    assert client.parse_campaigns(",  ,") is None
    # single and multiple UUIDs
    assert client.parse_campaigns("camp-1") == ["camp-1"]
    assert client.parse_campaigns("camp-1,camp-2") == ["camp-1", "camp-2"]
    # surrounding whitespace and blank entries are trimmed/dropped
    assert client.parse_campaigns("  camp-1 , , camp-2 ,") == ["camp-1", "camp-2"]


def test_fetch_scans_reads_data_wrapper_and_filters_by_creation_date():
    recent = 4102444800  # 2100, always within lookback
    old = 946684800  # 2000, always outside lookback
    with requests_mock.Mocker() as m:
        matcher = m.get(
            "https://thorcloud-lite.nextron-systems.com/api/v1/scan/search",
            json={"data": [{"id": "s1", "creation_date": recent}, {"id": "s2", "creation_date": old}], "total": 2},
        )
        scans = client.fetch_scans("https://thorcloud-lite.nextron-systems.com", client.get_headers("k"), days_back=7)
        assert [s["id"] for s in scans] == ["s1"]  # old one filtered out
        assert matcher.last_request.qs["order_field"] == ["creation_date"]
        # .qs lowercases values, so assert on the raw URL to prove the uppercase API enum is sent
        assert "order_dir=DESC" in matcher.last_request.url


def test_fetch_scans_campaign_param():
    with requests_mock.Mocker() as m:
        matcher = m.get(
            "https://thorcloud-lite.nextron-systems.com/api/v1/scan/search",
            json={"data": [], "total": 0},
        )
        client.fetch_scans(
            "https://thorcloud-lite.nextron-systems.com", client.get_headers("k"), days_back=7, campaigns=["camp-1"]
        )
        assert matcher.last_request.qs["campaign"] == ["camp-1"]


def test_scan_creation_epoch_handles_missing_and_millisecond_values():
    # no creation_date -> None
    assert client.scan_creation_epoch({}) is None
    # second-precision epoch is returned as-is (float)
    assert client.scan_creation_epoch({"creation_date": 1700000000}) == 1700000000.0
    # millisecond-precision epoch (> 1e12) is normalized to seconds
    assert client.scan_creation_epoch({"creation_date": 1700000000000}) == 1700000000.0


def test_fetch_scans_paginates_until_short_page():
    """A full page (len == limit) triggers another request; a short page ends it."""
    recent = 4102444800
    page1 = {"data": [{"id": "a", "creation_date": recent}, {"id": "b", "creation_date": recent}], "total": 3}
    page2 = {"data": [{"id": "c", "creation_date": recent}], "total": 3}
    with requests_mock.Mocker() as m:
        m.get(
            "https://thorcloud-lite.nextron-systems.com/api/v1/scan/search",
            [{"json": page1}, {"json": page2}],
        )
        scans = client.fetch_scans(
            "https://thorcloud-lite.nextron-systems.com", client.get_headers("k"), days_back=7, limit=2
        )
        assert [s["id"] for s in scans] == ["a", "b", "c"]


def test_fetch_scans_queries_each_campaign_in_turn():
    with requests_mock.Mocker() as m:
        m.get(
            "https://thorcloud-lite.nextron-systems.com/api/v1/scan/search",
            json={"data": [], "total": 0},
        )
        client.fetch_scans(
            "https://thorcloud-lite.nextron-systems.com",
            client.get_headers("k"),
            days_back=7,
            campaigns=["camp-1", "camp-2"],
        )
        queried = [r.qs["campaign"][0] for r in m.request_history]
        assert queried == ["camp-1", "camp-2"]


def test_fetch_scan_logs_skips_blank_and_malformed_lines():
    """Blank lines are ignored and a malformed NDJSON line is skipped, not fatal."""
    ndjson = "\n".join(['{"a": 1}', "", "not-json", '{"b": 2}'])
    with requests_mock.Mocker() as m:
        m.get("https://thorcloud-lite.nextron-systems.com/api/v1/scan/log", text=ndjson)
        events = client.fetch_scan_logs(
            "https://thorcloud-lite.nextron-systems.com", client.get_headers("k"), "uuid-1"
        )
        assert events == [{"a": 1}, {"b": 2}]


def test_fetch_scan_logs_uses_query_params_and_parses_ndjson():
    lines = [
        {"time": "2026-06-23T07:17:48Z", "level": "Notice", "scanid": "S-x", "message": "a"},
        {"time": "2026-06-23T07:17:49Z", "level": "Info", "scanid": "S-x", "message": "b"},
    ]
    ndjson = "\n".join(json.dumps(x) for x in lines)
    with requests_mock.Mocker() as m:
        matcher = m.get("https://thorcloud-lite.nextron-systems.com/api/v1/scan/log", text=ndjson)
        events = client.fetch_scan_logs(
            "https://thorcloud-lite.nextron-systems.com", client.get_headers("k"), "uuid-1"
        )
        assert len(events) == 2
        assert matcher.last_request.qs["scan"] == ["uuid-1"]
        assert matcher.last_request.qs["log"] == ["thor.json"]
