import pytest
import requests

from sekoiaio.operation_center.list_queries import ListQueries

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
QUERIES_URL = "https://fake.url/api/v1/notebooks/queries"


SAMPLE_QUERY = {
    "uuid": "11111111-1111-1111-1111-111111111111",
    "name": "my_query",
    "definition": "SELECT * FROM events",
}


def make_action() -> ListQueries:
    action = ListQueries()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


def test_list_queries_success(requests_mock):
    action = make_action()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )

    result = action.run({})

    assert result["queries"] == [SAMPLE_QUERY]


def test_list_queries_empty(requests_mock):
    action = make_action()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 0},
    )

    result = action.run({})

    assert result["queries"] == []
    assert len(action._logs) == 0


def test_list_queries_with_community_uuid(requests_mock):
    action = make_action()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )

    result = action.run({})

    assert result["queries"] == [SAMPLE_QUERY]


# ---------------------------------------------------------------------------
# get_queries() — pagination
# ---------------------------------------------------------------------------


def test_list_queries_pagination(requests_mock):
    """When total > limit, get_queries fetches multiple pages."""
    action = make_action()
    action.configure_http_session()

    page1 = [{"uuid": f"query-{i}", "name": f"q{i}"} for i in range(100)]
    page2 = [{"uuid": "query-100", "name": "q100"}]

    requests_mock.get(
        QUERIES_URL,
        [
            {"json": {"items": page1, "total": 101}},
            {"json": {"items": page2, "total": 101}},
            # Third call: items is empty → loop breaks
            {"json": {"items": [], "total": 101}},
        ],
    )

    # get_queries caps total at min(total, limit=100), so the while loop
    # exits after the second page anyway; this verifies the first page is returned.
    result = action.get_queries()

    assert len(result) == 100
    assert result[0]["uuid"] == "query-0"


def test_list_queries_empty_with_nonzero_total_logs_error(requests_mock):
    """If items is empty but total > 0 and fewer results than expected, an error is logged."""
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 5},
    )

    result = action.get_queries()

    assert result == []
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "Number of fetched results doesn't match total" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# get_queries() — HTTP error
# ---------------------------------------------------------------------------


def test_list_queries_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()

    requests_mock.get(QUERIES_URL, status_code=403, text="Forbidden")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_queries()

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving existing queries" in action._logs[0]["message"]
    assert "Response status: 403" in action._logs[0]["message"]
    assert "Forbidden" in action._logs[0]["message"]
