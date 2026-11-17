import pytest
import requests
from sekoia_automation.exceptions import AssetConnectorRateLimitError

from rapid7_insightvm.client import ApiClient

BASE_URL = "https://eu.api.insight.rapid7.com/vm/v4/integration"
ASSETS_URL = f"{BASE_URL}/assets"
VULNS_URL = f"{BASE_URL}/vulnerabilities"


@pytest.fixture
def client():
    return ApiClient(region="eu", api_key="fake_api_key")


def page(data, cursor=None, has_next=False, number=0, total_pages=1):
    links = [{"href": f"{ASSETS_URL}?page={number + 1}", "rel": "next"}] if has_next else []
    metadata = {"number": number, "size": 50, "totalPages": total_pages, "cursor": cursor}
    return {"data": data, "metadata": metadata, "links": links}


def test_client_configuration(client):
    assert client.base_url == BASE_URL
    assert client.verify is True
    assert client.headers["X-Api-Key"] == "fake_api_key"
    assert client.headers["Content-Type"] == "application/json"
    retry = client.get_adapter(BASE_URL).max_retries
    assert retry.respect_retry_after_header is False
    assert {"GET", "POST"} <= set(retry.allowed_methods)
    # M6: a 429 is not retried by urllib3, raise_for_status turns it into AssetConnectorRateLimitError
    assert 429 not in retry.status_forcelist
    assert retry.total == 5
    assert client.timeout == ApiClient.TIMEOUT


def test_client_retries_and_timeout_can_be_set():
    client = ApiClient.from_configuration({"region": "eu", "api_key": "k"}, nb_retries=1, timeout=(5, 30))
    assert client.get_adapter(BASE_URL).max_retries.total == 1
    assert client.timeout == (5, 30)


@pytest.mark.parametrize("region", ["", "eu.evil.example.com/", "eu/x", "e u", "attacker.example.com#"])
def test_client_refuses_an_invalid_region(region):
    """M7: the region is part of the host name."""
    with pytest.raises(ValueError, match="Invalid region"):
        ApiClient(region=region, api_key="key")


def test_client_normalises_the_region():
    assert ApiClient(region=" US2 ", api_key="key").base_url == (
        "https://us2.api.insight.rapid7.com/vm/v4/integration"
    )


def test_client_from_configuration():
    client = ApiClient.from_configuration({"region": "eu", "api_key": "fake_api_key"})
    assert client.base_url == BASE_URL
    with pytest.raises(TypeError):
        ApiClient.from_configuration(["eu"])


@pytest.mark.parametrize("header, expected", [(None, 300.0), ("120", 120.0), ("999999", 3600.0)])
def test_client_rate_limit_wait(header, expected):
    response = requests.Response()
    response.status_code = 429
    if header is not None:
        response.headers["Retry-After"] = header

    with pytest.raises(AssetConnectorRateLimitError) as error:
        ApiClient.raise_for_status(response)
    assert error.value.retry_after == expected


def test_error_message_includes_the_api_message():
    response = requests.Response()
    response.status_code = 500
    response._content = b'{"message": "detail"}'
    assert ApiClient.error_message(requests.HTTPError("500", response=response)).endswith(" - detail")
    response._content = b"not json"
    assert ApiClient.error_message(requests.HTTPError("500", response=response)) == "500"
    assert ApiClient.error_message(requests.ConnectionError("down")) == "down"


def test_next_cursor():
    next_link = {"href": f"{ASSETS_URL}?page=1&cursor=abc", "rel": "next"}
    assert ApiClient.next_cursor({"metadata": {"cursor": "meta"}, "links": [next_link]}) == (True, "meta")
    assert ApiClient.next_cursor({"metadata": {"cursor": None}, "links": [next_link]}) == (True, "abc")
    assert ApiClient.next_cursor({"links": [{"href": f"{ASSETS_URL}?page=1", "rel": "next"}]}) == (True, None)
    assert ApiClient.next_cursor({"metadata": {"cursor": "meta"}, "links": []}) == (False, None)


def test_iter_asset_pages_follows_the_cursor(client, requests_mock):
    assets = requests_mock.post(
        ASSETS_URL,
        [
            {"json": page([{"id": "a"}], cursor="c1", has_next=True, total_pages=2)},
            {"json": page([{"id": "b"}], number=1, total_pages=2)},
        ],
    )

    pages = list(
        client.iter_asset_pages(
            current_time="2026-10-28T11:00:00Z",
            comparison_time="2026-10-28T10:00:00Z",
            page_size=50,
        )
    )

    assert [(p.number, p.cursor, p.data) for p in pages] == [(0, None, [{"id": "a"}]), (1, "c1", [{"id": "b"}])]
    first, second = (request.qs for request in assets.request_history)
    assert first == {
        "size": ["50"],
        "sort": ["id,asc"],
        "currenttime": ["2026-10-28t11:00:00z"],
        "comparisontime": ["2026-10-28t10:00:00z"],
        "includesame": ["true"],
        "includeuniqueidentifiers": ["false"],
    }
    assert (second["page"], second["cursor"]) == (["1"], ["c1"])
    assert all(request.json() == {} for request in assets.request_history)


def test_iter_asset_pages_resumes_from_a_page(client, requests_mock):
    assets = requests_mock.post(ASSETS_URL, json=page([]))

    [only] = client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T11:00:00Z", 50, page=3, cursor="c3")

    assert (only.number, only.cursor) == (3, "c3")
    query = assets.last_request.qs
    assert (query["page"], query["cursor"], query["includesame"]) == (["3"], ["c3"], ["true"])


def test_iter_asset_pages_raises_on_errors(client, requests_mock):
    requests_mock.post(ASSETS_URL, status_code=400, json={"message": "bad cursor"})
    with pytest.raises(requests.HTTPError):
        list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T11:00:00Z", 50))


def test_iter_asset_pages_follows_empty_pages(client, requests_mock):
    requests_mock.post(
        ASSETS_URL,
        [
            {"json": page([], cursor="c1", has_next=True, total_pages=2)},
            {"json": page([{"id": "b"}], number=1, total_pages=2)},
        ],
    )

    pages = list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))

    assert [p.data for p in pages] == [[], [{"id": "b"}]]


def test_pagination_stops_when_the_cursor_does_not_advance(client, requests_mock):
    requests_mock.post(ASSETS_URL, json=page([{"id": "a"}], cursor="stuck", has_next=True))
    requests_mock.post(VULNS_URL, json=page([{"id": "v"}], cursor="stuck", has_next=True))

    with pytest.raises(RuntimeError):
        list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))
    with pytest.raises(RuntimeError):
        list(client.search_vulnerabilities(["v"]))


def test_iter_asset_pages_stops_on_an_empty_last_page(client, requests_mock):
    """M8: an empty page at or past the last announced page ends the traversal, even with a next link."""
    assets = requests_mock.post(
        ASSETS_URL,
        [
            {"json": page([{"id": "a"}], cursor="c1", has_next=True, total_pages=2)},
            {"json": page([], cursor="c2", has_next=True, number=1, total_pages=2)},
        ],
    )

    pages = list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))

    assert [p.number for p in pages] == [0, 1]
    assert assets.call_count == 2


def test_pagination_fails_far_past_the_announced_pages(client, requests_mock):
    """M8: a next link that never ends raises past totalPages + 10, on both endpoints."""
    counter = {"n": 0}

    def endless(request, context):
        counter["n"] += 1
        return page([{"id": "a"}], cursor=f"c{counter['n']}", has_next=True, total_pages=2)

    requests_mock.post(ASSETS_URL, json=endless)
    with pytest.raises(RuntimeError, match="do not end"):
        list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))
    assert counter["n"] == 12

    counter["n"] = 0
    requests_mock.post(VULNS_URL, json=endless)
    with pytest.raises(RuntimeError, match="do not end"):
        list(client.search_vulnerabilities(["v"]))
    assert counter["n"] == 12


def endless_pages(total_pages=None, data=None):
    """A callback answering a new cursor and a next link on every request."""
    counter = {"n": 0}

    def answer(request, context):
        counter["n"] += 1
        return page(
            [{"id": "a"}] if data is None else data, cursor=f"c{counter['n']}", has_next=True, total_pages=total_pages
        )

    answer.counter = counter
    return answer


def test_pagination_without_total_pages_stops_on_an_empty_page(client, requests_mock):
    """Without totalPages, an empty page with a next link and a new cursor ends the traversal, on both endpoints."""
    assets = requests_mock.post(
        ASSETS_URL,
        [
            {"json": page([{"id": "a"}], cursor="c1", has_next=True, total_pages=None)},
            {"json": page([], cursor="c2", has_next=True, number=1, total_pages=None)},
        ],
    )
    pages = list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))
    assert [p.number for p in pages] == [0, 1]
    assert assets.call_count == 2

    vulns = requests_mock.post(VULNS_URL, json=endless_pages(total_pages=None, data=[]))
    assert list(client.search_vulnerabilities(["v1"])) == []
    assert vulns.call_count == 1


def test_pagination_fails_past_the_absolute_cap(client, requests_mock, monkeypatch):
    """Without totalPages, pages that never end raise at MAX_PAGES, on both endpoints."""
    monkeypatch.setattr(ApiClient, "MAX_PAGES", 5)

    assets = endless_pages()
    requests_mock.post(ASSETS_URL, json=assets)
    with pytest.raises(RuntimeError, match="do not end: 5 pages read"):
        list(client.iter_asset_pages("2026-10-28T11:00:00Z", "2026-10-28T10:00:00Z", 50))
    assert assets.counter["n"] == 5

    vulns = endless_pages()
    requests_mock.post(VULNS_URL, json=vulns)
    with pytest.raises(RuntimeError, match="do not end: 5 pages read"):
        list(client.search_vulnerabilities(["v"]))
    assert vulns.counter["n"] == 5


def test_search_vulnerabilities_stops_on_an_empty_last_page(client, requests_mock):
    vulns = requests_mock.post(VULNS_URL, json=page([], cursor="vc", has_next=True, total_pages=1))

    assert list(client.search_vulnerabilities(["v1"])) == []
    assert vulns.call_count == 1


def test_vulnerability_ids_are_escaped():
    assert ApiClient.id_filter(["a'b", "c\\d"]) == "vulnerability.id IN ['a\\'b', 'c\\\\d']"


def test_search_vulnerabilities_follows_the_pages(client, requests_mock):
    vulns = requests_mock.post(
        VULNS_URL,
        [
            {"json": page([{"id": "v1"}], cursor="vc", has_next=True)},
            {"json": page([{"id": "v2"}])},
        ],
    )

    assert [raw["id"] for raw in client.search_vulnerabilities(["v1", "v2"])] == ["v1", "v2"]
    first, second = vulns.request_history
    assert first.json() == second.json() == {"vulnerability": "vulnerability.id IN ['v1', 'v2']"}
    assert (second.qs["page"], second.qs["cursor"]) == (["1"], ["vc"])
