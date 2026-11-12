import pytest

from tests.payloads import BASE, search_payload
from urlscan_modules.action.action_search import Search
from urlscan_modules.formatters import build_indicator_query

FIRST_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def action(module, tmp_path):
    return Search(module=module, data_path=tmp_path)


@pytest.fixture
def route(api):
    return api.get("/api/v1/search/")


def params(route) -> dict[str, str]:
    return dict(route.calls.last.request.url.params)


@pytest.mark.parametrize(
    "indicator, expected_query",
    [
        ("203.0.113.10", 'ip:"203.0.113.10"'),
        ("2606:4700::6812:179a", 'ip:"2606:4700::6812:179a"'),
        (
            "25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484",
            'hash:"25ddf2c883e0d1958ea971d279a7e4f0fd446724ee3db7db19dadabd4a62e484"',
        ),
        (" https://example.com/ ", 'page.url:"https://example.com/"'),
        ('https://example.com/?a="b"', 'page.url:"https://example.com/?a=\\"b\\""'),
        ("example.com", 'domain:"example.com"'),
    ],
)
def test_build_indicator_query(indicator, expected_query):
    assert build_indicator_query(indicator) == expected_query


def test_search_with_indicator(action, route):
    route.respond(200, json=search_payload(2))

    result = action.run({"indicator": "example.com"})

    assert params(route) == {"q": 'domain:"example.com"', "size": "100"}
    assert result["query"] == 'domain:"example.com"'
    assert result["total"] == 5
    assert result["has_more"] is False
    assert result["took"] == 3
    assert result["search_date_limit_days"] is None
    assert result["next_search_after"] is None
    assert len(result["results"]) == 2
    assert result["results"][0] == {
        "uuid": FIRST_ID,
        "scan_time": "2026-11-02T23:58:34.078Z",
        "submitted_url": "https://example.com/",
        "visibility": "public",
        "page_url": "https://example.com/",
        "page_domain": "example.com",
        "page_ip": "203.0.113.10",
        "page_asn": "AS64500",
        "page_asn_name": "EXAMPLE-AS, US",
        "page_country": "US",
        "page_title": "Example Domain",
        "page_status": "200",
        "malicious": False,
        "score": 0,
        "report_url": f"{BASE}/result/{FIRST_ID}/",
        "result_api_url": f"{BASE}/api/v1/result/{FIRST_ID}/",
        "screenshot_url": f"{BASE}/screenshots/{FIRST_ID}.png",
        "files": [
            {
                "filename": "a.zip",
                "sha256": "ab" * 32,
                "size": 10,
                "mime_type": "application/zip",
                "mime_description": "Zip archive",
                "url": "https://example.com/a.zip",
                "state": "completed",
            }
        ],
    }


def test_search_with_query_and_pagination(action, route):
    route.respond(200, json=search_payload(2))

    result = action.run({"query": 'task.tags:"phishing"', "size": 2, "search_after": "1,abc"})

    assert params(route) == {"q": 'task.tags:"phishing"', "size": "2", "search_after": "1,abc"}
    assert result["query"] == 'task.tags:"phishing"'
    assert result["next_search_after"] == "1793663105645,id-1"


def test_null_size_uses_default(action, route):
    route.respond(200, json=search_payload(2))

    action.run({"indicator": "example.com", "size": None, "search_after": None})

    assert params(route) == {"q": 'domain:"example.com"', "size": "100"}


def test_empty_page(action, route):
    route.respond(200, json={"total": 0, "took": 1, "has_more": False, "results": []})

    result = action.run({"indicator": "example.com"})

    assert result["results"] == []
    assert result["next_search_after"] is None


def test_search_date_limit(action, route):
    route.respond(200, json=search_payload(2) | {"search_date_limit_days": 30})

    result = action.run({"indicator": "example.com"})

    assert result["search_date_limit_days"] == 30


@pytest.mark.parametrize(
    "arguments",
    [{}, {"indicator": "a", "query": "b"}, {"indicator": " ", "query": ""}],
)
def test_exactly_one_of_indicator_and_query(action, api, arguments):
    assert action.run(arguments) is None

    assert action.error_message == 'Provide exactly one of "indicator" or "query"'
    assert api.calls.call_count == 0


def test_api_validation_error(action, route):
    route.respond(400, json={"message": 'ValidationError: "size" must be less than or equal to 10000'})

    assert action.run({"indicator": "example.com", "size": 10001}) is None

    assert action.error_message == (
        'urlscan.io API error 400: ValidationError: "size" must be less than or equal to 10000'
    )
    assert params(route)["size"] == "10001"
