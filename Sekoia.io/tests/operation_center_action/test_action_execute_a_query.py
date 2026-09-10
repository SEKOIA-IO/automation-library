import re
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4

import pytest
import requests
from requests.exceptions import HTTPError

from sekoiaio.operation_center.execute_a_query import (
    ExecuteAQuery,
    QueryExecutionError,
    QueryListingError,
    ExecuteAQueryArguments,
)

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
QUERIES_URL = "https://fake.url/api/v1/notebooks/queries"
QUERY_RUNS_URL = "https://fake.url/api/v1/notebooks/queries/runs"

SAMPLE_QUERY_RUN = {
    "task_id": str(uuid4()),
    "uuid": str(uuid4()),
}

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
        "ql_query": "events\n| where timestamp between (?time.start .. ?time.end)\n| limit 2",
        "community_uuids": [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222212",
            "33333333-3333-3333-3333-333333333333",
        ],
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


def make_action() -> ExecuteAQuery:
    action = ExecuteAQuery()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# run() — happy path via query_uuid
# ---------------------------------------------------------------------------


def test_execute_query_by_uuid_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json=SAMPLE_QUERY_RUN)
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text='{"event.action": "login"}\n{"event.action": "logout"}\n',
    )

    result = action.run(
        {
            "query_uuid": SAMPLE_QUERY["uuid"],
            "result_format": "jsonl",
        }
    )

    assert result["query_result"] == '{"event.action": "login"}\n{"event.action": "logout"}\n'


def test_execute_query_by_uuid_csv_format(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json=SAMPLE_QUERY_RUN)
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text="event.action\nlogin\nlogout\n",
    )

    result = action.run(
        {
            "query_uuid": SAMPLE_QUERY["uuid"],
            "result_format": "csv",
        }
    )

    assert result["query_result"] == "event.action\nlogin\nlogout\n"
    assert requests_mock.last_request.qs["download_format"] == ["csv"]


# ---------------------------------------------------------------------------
# run() — happy path via query_name
# ---------------------------------------------------------------------------


def test_execute_query_by_name_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": SAMPLE_QUERY_RUN["uuid"]})
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text="result_data",
    )

    result = action.run(
        {
            "query_name": "my_query",
            "result_format": "jsonl",
        }
    )

    assert result["query_result"] == "result_data"
    assert requests_mock.request_history[0].qs["match[name]"] == ["my_query"]


# ---------------------------------------------------------------------------
# run() happy path & Result saved in file
# ---------------------------------------------------------------------------


def test_execute_query_save_to_file(requests_mock, tmp_path):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()
    action._data_path = tmp_path

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json=SAMPLE_QUERY_RUN)
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text='{"event.action": "login"}\n{"event.action": "logout"}\n',
    )
    argument = ExecuteAQueryArguments(query_uuid=SAMPLE_QUERY["uuid"], result_format="csv", to_file=True)

    result = action.run(arguments=argument)

    assert result["output_path"] is not None
    assert re.match(r"^query_output-[0-9a-f-]{36}\.csv$", result["output_path"])


# ---------------------------------------------------------------------------
# get_query_by_name() — edge cases
# ---------------------------------------------------------------------------


def test_get_query_by_name_multiple_results_raises(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        QUERIES_URL,
        json={
            "items": [SAMPLE_QUERY, {**SAMPLE_QUERY, "uuid": str(uuid4())}],
            "total": 2,
        },
    )

    with pytest.raises(QueryListingError):
        action.get_query_by_name("sample query")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "found 2 queries" in action._logs[0]["message"]
    assert "sample query" in action._logs[0]["message"]


def test_get_query_by_name_empty_results_raises(requests_mock):

    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 0},
    )

    with pytest.raises(QueryListingError):
        action.get_query_by_name("nonexistent_query")
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "No query found with name 'nonexistent_query'" in action._logs[0]["message"]


def test_get_query_by_name_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(QUERIES_URL, status_code=500, text="Internal Server Error")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_query_by_name("my_query")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving existing queries matching" in action._logs[0]["message"]
    assert "Response status: 500" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# get_query_by_uuid() — HTTP error
# ---------------------------------------------------------------------------


def test_get_query_by_uuid_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", status_code=404, text="Not Found")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_query_by_uuid(UUID(SAMPLE_QUERY["uuid"]))

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving query definition" in action._logs[0]["message"]
    assert "Response status: 404" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# trigger_query_execution() — HTTP error
# ---------------------------------------------------------------------------


def test_trigger_query_execution_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.post(QUERY_RUNS_URL, status_code=422, text="Unprocessable Entity")

    with pytest.raises(requests.exceptions.HTTPError):
        action.trigger_query_execution(
            query_uuid=UUID(SAMPLE_QUERY["uuid"]),
            query_definition={"ql_query": "SELECT * FROM events"},
            query_parameters=None,
        )

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when triggering query execution" in action._logs[0]["message"]
    assert "Response status: 422" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# _wait_for_query_completion_step() — error status
# ---------------------------------------------------------------------------


def test_wait_for_query_completion_error_status_raises(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}",
        json={"status": "error", "error": "query syntax error"},
    )

    with pytest.raises(QueryExecutionError):
        action._wait_for_query_completion_step(
            SAMPLE_QUERY_RUN["uuid"], lambda status: status == "pending", timeout=60
        )

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "ended with error" in action._logs[0]["message"]
    assert "query syntax error" in action._logs[0]["message"]


def test_wait_for_query_completion_step_http_error_raises(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}",
        status_code=500,
        text="Server Error",
    )

    with pytest.raises(HTTPError):
        action._wait_for_query_completion_step(
            SAMPLE_QUERY_RUN["uuid"], lambda status: status == "pending", timeout=60
        )

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving query run status" in action._logs[0]["message"]
    assert "Response status: 500" in action._logs[0]["message"]


def test_wait_for_query_completion_polls_until_done(requests_mock):
    """Status transitions: pending → done; time.sleep is patched to avoid delays."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}",
        [
            {"json": {"status": "pending"}},
            {"json": {"status": "done"}},
        ],
    )

    with patch("sekoiaio.operation_center.execute_a_query.sleep"):
        action._wait_for_query_completion_step(
            SAMPLE_QUERY_RUN["uuid"], lambda status: status == "pending", timeout=60
        )

    assert requests_mock.call_count == 2


def test_wait_for_query_completion_error_in_loop(requests_mock):
    """Error status returned during polling loop raises QueryExecutionError."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}",
        [
            {"json": {"status": "pending"}},
            {"json": {"status": "error", "error": "timeout in cluster"}},
        ],
    )

    with patch("sekoiaio.operation_center.execute_a_query.sleep"):
        with pytest.raises(QueryExecutionError):
            action._wait_for_query_completion_step(
                SAMPLE_QUERY_RUN["uuid"], lambda status: status == "pending", timeout=60
            )

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "timeout in cluster" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# download_query_result() — HTTP error
# ---------------------------------------------------------------------------


def test_download_query_result_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        status_code=410,
        text="Gone: result expired",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.download_query_result(SAMPLE_QUERY_RUN["uuid"], "jsonl")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when downloading query result" in action._logs[0]["message"]
    assert "Response status: 410" in action._logs[0]["message"]
    assert "Gone: result expired" in action._logs[0]["message"]


def test_download_query_result_no_results_returns_none(requests_mock):
    """A 404 with NO_RESULTS code should return None instead of raising."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        status_code=404,
        json={"detail": {"message": "There is no results to download", "code": "NO_RESULTS"}},
    )

    result = action.download_query_result(SAMPLE_QUERY_RUN["uuid"], "jsonl")

    assert result is None
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "info"
    assert "no results" in action._logs[0]["message"].lower()


def test_download_query_result_404_non_no_results_raises(requests_mock):
    """A 404 without NO_RESULTS code should still raise an HTTPError."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        status_code=404,
        json={"detail": {"message": "Run not found", "code": "NOT_FOUND"}},
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.download_query_result(SAMPLE_QUERY_RUN["uuid"], "jsonl")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when downloading query result" in action._logs[0]["message"]


def test_run_no_results_returns_gracefully(requests_mock):
    """When the query run has no results the action should finish without error."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json=SAMPLE_QUERY_RUN)
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        status_code=404,
        json={"detail": {"message": "There is no results to download", "code": "NO_RESULTS"}},
    )

    result = action.run({"query_uuid": SAMPLE_QUERY["uuid"], "result_format": "jsonl"})

    assert result["query_result"] is None
    assert result["output_path"] is None


# ---------------------------------------------------------------------------
# run() — full polling cycle (pending → running → done)
# ---------------------------------------------------------------------------


def test_execute_query_full_polling_cycle(requests_mock):
    """Verify wait_for_query_completion handles pending → running → done transitions."""
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": SAMPLE_QUERY_RUN["uuid"]})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}",
        [
            {"json": {"status": "pending"}},  # _wait_for_query_completion_step #1 initial
            {"json": {"status": "running"}},  # _wait_for_query_completion_step #1 loop exit
            {"json": {"status": "running"}},  # _wait_for_query_completion_step #2 initial
            {"json": {"status": "done"}},  # _wait_for_query_completion_step #2 loop exit
        ],
    )
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text="final_result",
    )

    with patch("sekoiaio.operation_center.execute_a_query.sleep"):
        result = action.run(
            {
                "query_uuid": SAMPLE_QUERY["uuid"],
                "result_format": "jsonl",
            }
        )

    assert result["query_result"] == "final_result"


def test_execute_query_omits_community_uuids(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(f"{QUERIES_URL}/{SAMPLE_QUERY['uuid']}", json=SAMPLE_QUERY)
    requests_mock.get(f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{SAMPLE_QUERY_RUN['uuid']}/download",
        text="final_result",
    )

    action.trigger_query_execution = MagicMock()
    action.trigger_query_execution.return_value = SAMPLE_QUERY_RUN["uuid"]

    action.run(
        {
            "query_uuid": SAMPLE_QUERY["uuid"],
            "result_format": "jsonl",
        }
    )

    # Make sure community_uuids was not sent
    expected_definition = dict(SAMPLE_QUERY["definition"])
    del expected_definition["community_uuids"]
    action.trigger_query_execution.assert_called_with(
        query_uuid=UUID(SAMPLE_QUERY["uuid"]), query_definition=expected_definition, query_parameters=None
    )
