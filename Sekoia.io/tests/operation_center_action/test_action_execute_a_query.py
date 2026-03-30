from unittest.mock import patch
from uuid import UUID

import pytest
import requests

from sekoiaio.operation_center.execute_a_query import ExecuteAQuery, QueryExecutionError, QueryListingError

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
QUERIES_URL = "https://fake.url/api/v1/notebooks/queries"
QUERY_RUNS_URL = "https://fake.url/api/v1/notebooks/queries/runs"

QUERY_UUID = "11111111-1111-1111-1111-111111111111"
RUN_UUID = "33333333-3333-3333-3333-333333333333"

SAMPLE_QUERY = {
    "uuid": QUERY_UUID,
    "name": "my_query",
    "definition": "SELECT * FROM events",
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

    requests_mock.get(f"{QUERIES_URL}/{QUERY_UUID}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": RUN_UUID})
    requests_mock.get(f"{QUERY_RUNS_URL}/{RUN_UUID}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}/download",
        text='{"event": "login"}\n',
    )

    result = action.run(
        {
            "query_uuid": QUERY_UUID,
            "result_format": "jsonl",
        }
    )

    assert result["query_result"] == '{"event": "login"}\n'


def test_execute_query_by_uuid_csv_format(requests_mock):
    action = make_action()

    requests_mock.get(f"{QUERIES_URL}/{QUERY_UUID}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": RUN_UUID})
    requests_mock.get(f"{QUERY_RUNS_URL}/{RUN_UUID}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}/download",
        text="event\nlogin\n",
    )

    result = action.run(
        {
            "query_uuid": QUERY_UUID,
            "result_format": "csv",
        }
    )

    assert result["query_result"] == "event\nlogin\n"
    assert requests_mock.last_request.qs["download_format"] == ["csv"]


# ---------------------------------------------------------------------------
# run() — happy path via query_name
# ---------------------------------------------------------------------------


def test_execute_query_by_name_success(requests_mock):
    action = make_action()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [SAMPLE_QUERY], "total": 1},
    )
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": RUN_UUID})
    requests_mock.get(f"{QUERY_RUNS_URL}/{RUN_UUID}", json={"status": "done"})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}/download",
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
# get_query_by_name() — edge cases
# ---------------------------------------------------------------------------


def test_get_query_by_name_multiple_results_raises(requests_mock):
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        QUERIES_URL,
        json={
            "items": [SAMPLE_QUERY, {**SAMPLE_QUERY, "uuid": "44444444-4444-4444-4444-444444444444"}],
            "total": 2,
        },
    )

    with pytest.raises(QueryListingError):
        action.get_query_by_name("my_query")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "found 2 queries" in action._logs[0]["message"]
    assert "my_query" in action._logs[0]["message"]


def test_get_query_by_name_empty_results_raises(requests_mock):
    """When no query matches, results[0] raises IndexError."""
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        QUERIES_URL,
        json={"items": [], "total": 0},
    )

    with pytest.raises(IndexError):
        action.get_query_by_name("nonexistent_query")


def test_get_query_by_name_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()

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

    requests_mock.get(f"{QUERIES_URL}/{QUERY_UUID}", status_code=404, text="Not Found")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_query_by_uuid(UUID(QUERY_UUID))

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

    requests_mock.post(QUERY_RUNS_URL, status_code=422, text="Unprocessable Entity")

    with pytest.raises(requests.exceptions.HTTPError):
        action.trigger_query_execution(
            query_uuid=UUID(QUERY_UUID),
            query_definition="SELECT * FROM events",
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

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}",
        json={"status": "error", "error": "query syntax error"},
    )

    with pytest.raises(QueryExecutionError):
        action._wait_for_query_completion_step(RUN_UUID, lambda status: status == "pending", timeout=60)

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "ended with error" in action._logs[0]["message"]
    assert "query syntax error" in action._logs[0]["message"]


def test_wait_for_query_completion_step_http_error_raises(requests_mock):
    action = make_action()
    action.configure_http_session()

    requests_mock.get(f"{QUERY_RUNS_URL}/{RUN_UUID}", status_code=500, text="Server Error")

    with pytest.raises(QueryExecutionError):
        action._wait_for_query_completion_step(RUN_UUID, lambda status: status == "pending", timeout=60)

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving query run status" in action._logs[0]["message"]
    assert "Response status: 500" in action._logs[0]["message"]


def test_wait_for_query_completion_polls_until_done(requests_mock):
    """Status transitions: pending → done; time.sleep is patched to avoid delays."""
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}",
        [
            {"json": {"status": "pending"}},
            {"json": {"status": "done"}},
        ],
    )

    with patch("sekoiaio.operation_center.execute_a_query.time.sleep"):
        action._wait_for_query_completion_step(RUN_UUID, lambda status: status == "pending", timeout=60)

    assert requests_mock.call_count == 2


def test_wait_for_query_completion_error_in_loop(requests_mock):
    """Error status returned during polling loop raises QueryExecutionError."""
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}",
        [
            {"json": {"status": "pending"}},
            {"json": {"status": "error", "error": "timeout in cluster"}},
        ],
    )

    with patch("sekoiaio.operation_center.execute_a_query.time.sleep"):
        with pytest.raises(QueryExecutionError):
            action._wait_for_query_completion_step(RUN_UUID, lambda status: status == "pending", timeout=60)

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "timeout in cluster" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# download_query_result() — HTTP error
# ---------------------------------------------------------------------------


def test_download_query_result_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()

    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}/download",
        status_code=410,
        text="Gone: result expired",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.download_query_result(RUN_UUID, "jsonl")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when downloading query result" in action._logs[0]["message"]
    assert "Response status: 410" in action._logs[0]["message"]
    assert "Gone: result expired" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# run() — full polling cycle (pending → running → done)
# ---------------------------------------------------------------------------


def test_execute_query_full_polling_cycle(requests_mock):
    """Verify wait_for_query_completion handles pending → running → done transitions."""
    action = make_action()

    requests_mock.get(f"{QUERIES_URL}/{QUERY_UUID}", json=SAMPLE_QUERY)
    requests_mock.post(QUERY_RUNS_URL, json={"uuid": RUN_UUID})
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}",
        [
            {"json": {"status": "pending"}},  # _wait_for_query_completion_step #1 initial
            {"json": {"status": "running"}},  # _wait_for_query_completion_step #1 loop exit
            {"json": {"status": "running"}},  # _wait_for_query_completion_step #2 initial
            {"json": {"status": "done"}},  # _wait_for_query_completion_step #2 loop exit
        ],
    )
    requests_mock.get(
        f"{QUERY_RUNS_URL}/{RUN_UUID}/download",
        text="final_result",
    )

    with patch("sekoiaio.operation_center.execute_a_query.time.sleep"):
        result = action.run(
            {
                "query_uuid": QUERY_UUID,
                "result_format": "jsonl",
            }
        )

    assert result["query_result"] == "final_result"
