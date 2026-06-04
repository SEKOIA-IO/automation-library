import pytest
import requests
from uuid import uuid4

from sekoiaio.operation_center.list_queries import ListQueries, ListQueriesArguments

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
QUERIES_URL = "https://fake.url/api/v1/notebooks/queries"


SAMPLE_QUERY: dict = {
    "uuid": str(uuid4()),
    "community_uuid": str(uuid4()),
    "shared_with": None,
    "created_by": str(uuid4()),
    "created_by_type": "user",
    "created_at": "1970-01-01T00:00:00.000000Z",
    "updated_at": "1970-01-01T00:00:00.000000Z",
    "name": "sample query",
    "description": "",
    "described_by_ai": None,
    "definition": {
        "ql_query": "events\n| where timestamp between (?time.start .. ?time.end)\n| limit 100",
        "community_uuids": [],
        "intake_uuids": None,
        "parent_community_uuid": None,
        "is_shared_run": False,
    },
    "visualization": "table",
    "visualization_params": {
        "x": None,
        "y": None,
        "breakdown": None,
        "stacked": None,
        "unit": None,
        "columns": None,
    },
    "last_run_uuid": None,
    "parameters": ["time"],
    "datasets": [],
}


def make_action() -> ListQueries:
    action = ListQueries()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


def test_list_queries_success(requests_mock):

    requests_mock.get(
        QUERIES_URL,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )
    action = make_action()
    action.configure_http_session()
    action.configure_urls()
    result = action.run(ListQueriesArguments())

    assert result["queries"][0] == SAMPLE_QUERY


def test_list_queries_empty(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 0},
    )

    result = action.run(ListQueriesArguments())

    assert result["queries"] == []
    assert len(action._logs) == 0


# ---------------------------------------------------------------------------
# get_queries() — pagination
# ---------------------------------------------------------------------------


def test_list_queries_pagination(requests_mock):
    """When total > limit, get_queries fetches multiple pages."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

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

    # get_queries uses the API-provided total to drive pagination. In this test,
    # the first two responses provide all 101 results, and the mocked empty third
    # page causes the loop to stop.
    result = action.get_queries(ListQueriesArguments())

    assert len(result) == 101
    for i in range(101):
        assert result[i]["uuid"] == f"query-{i}"
        assert result[i]["name"] == f"q{i}"


def test_list_queries_empty_with_nonzero_total_logs_error(requests_mock):
    """If items is empty but total > 0 and fewer results than expected, an error is logged."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 5},
    )

    result = action.get_queries(ListQueriesArguments())

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
    action.configure_urls()

    requests_mock.get(QUERIES_URL, status_code=403, text="Forbidden")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_queries(ListQueriesArguments())

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving existing queries" in action._logs[0]["message"]
    assert "Response status: 403" in action._logs[0]["message"]
    assert "Forbidden" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# run()  — Filters passed to get_queries
# ---------------------------------------------------------------------------


def test_list_queries_filters(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    def match_request(request):
        params = request.qs
        assert params["match[uuid]"] == ["some-uuid"]
        assert params["match[name]"] == ["some-name"]
        assert params["match[visualization]"] == ["some-vis"]
        assert params["match[is_shared]"] == ["true"]
        assert params["match[created_by]"] == ["creator-uuid"]
        assert params["parameters"] == ["username"]
        return True

    requests_mock.get(
        QUERIES_URL,
        additional_matcher=match_request,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )

    arguments = ListQueriesArguments(
        match_uuid="some-uuid",
        match_name="some-name",
        match_visualization="some-vis",
        match_isshared=True,
        match_created_by="creator-uuid",
        parameters="username",
    )
    result = action.run(arguments)

    assert result["queries"][0] == SAMPLE_QUERY
