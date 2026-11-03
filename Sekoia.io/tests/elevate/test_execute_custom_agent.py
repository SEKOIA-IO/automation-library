from unittest.mock import patch
from uuid import uuid4

import pytest
from requests.exceptions import HTTPError, ReadTimeout

from sekoiaio.elevate.execute_custom_agent import (
    AgentExecutionError,
    ExecuteCustomAgent,
)

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
AGENTS_URL = "https://fake.url/api/v1/generative/agents"
AGENT_RUNS_URL = "https://fake.url/api/v1/generative/agent-runs"

PLAYBOOK_UUID = str(uuid4())
PLAYBOOK_RUN_UUID = str(uuid4())
NODE_RUN_UUID = str(uuid4())

SAMPLE_AGENT: dict = {
    "uuid": str(uuid4()),
    "community_uuid": str(uuid4()),
    "name": "Triage agent",
    "instructions": "Summarize the alert",
    "tools": ["get_alert"],
    "skill_uuids": [str(uuid4())],
    "response_format": {"type": "object", "properties": {"summary": {"type": "string"}}},
}

AGENT_RUN_UUID = str(uuid4())


def make_agent_run(status: str, **extra) -> dict:
    return {
        "uuid": AGENT_RUN_UUID,
        "community_uuid": SAMPLE_AGENT["community_uuid"],
        "agent_uuid": SAMPLE_AGENT["uuid"],
        "run_name": None,
        "status": status,
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:12Z",
        "duration_seconds": 12.5,
        "credits": "0.42",
        "output": {"summary": "benign"},
        **extra,
    }


def make_action() -> ExecuteCustomAgent:
    action = ExecuteCustomAgent()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    action.module._playbook_uuid = PLAYBOOK_UUID
    action.module._playbook_run_uuid = PLAYBOOK_RUN_UUID
    action.module._node_run_uuid = NODE_RUN_UUID
    return action


def mock_agent_and_run_creation(requests_mock) -> None:
    requests_mock.get(f"{AGENTS_URL}/{SAMPLE_AGENT['uuid']}", json=SAMPLE_AGENT)
    requests_mock.post(AGENT_RUNS_URL, json={"uuid": AGENT_RUN_UUID})


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


def test_execute_custom_agent_success(requests_mock):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("completed"))

    with patch("sekoiaio.elevate.execute_custom_agent.sleep"):
        result = action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert result["uuid"] == AGENT_RUN_UUID
    assert result["agent_uuid"] == SAMPLE_AGENT["uuid"]
    assert result["community_uuid"] == SAMPLE_AGENT["community_uuid"]
    assert result["status"] == "completed"
    assert result["run_name"] is None
    assert result["duration_seconds"] == 12.5
    assert result["credits"] == "0.42"
    assert result["output"] == {"summary": "benign"}


def test_execute_custom_agent_sends_api_key(requests_mock):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("completed"))

    with patch("sekoiaio.elevate.execute_custom_agent.sleep"):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    for request in requests_mock.request_history:
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"


def test_execute_custom_agent_run_body(requests_mock):
    """The run is created from the agent definition and scoped to the current playbook run."""
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("completed"))

    with patch("sekoiaio.elevate.execute_custom_agent.sleep"):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    create_request = next(r for r in requests_mock.request_history if r.method == "POST")
    assert create_request.url == AGENT_RUNS_URL
    body = create_request.json()
    assert body["community_uuid"] == SAMPLE_AGENT["community_uuid"]
    assert body["scope_type"] == "playbook_run"
    assert body["scope_uuid"] == PLAYBOOK_RUN_UUID
    assert body["agent"] == {
        "key": f"{PLAYBOOK_UUID}:{PLAYBOOK_RUN_UUID}+{NODE_RUN_UUID}",
        "instructions": SAMPLE_AGENT["instructions"],
        "tools": SAMPLE_AGENT["tools"],
        "skill_uuids": SAMPLE_AGENT["skill_uuids"],
        "response_format": SAMPLE_AGENT["response_format"],
    }


@pytest.mark.parametrize(
    "output",
    [
        ["a", "b"],
        "plain text answer",
        42,
        True,
        None,
    ],
)
def test_execute_custom_agent_output_types(requests_mock, output):
    """The manifest allows any JSON type as output, depending on the agent response_format."""
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("completed", output=output))

    with patch("sekoiaio.elevate.execute_custom_agent.sleep"):
        result = action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert result["output"] == output


# ---------------------------------------------------------------------------
# run() — polling
# ---------------------------------------------------------------------------


def test_execute_custom_agent_polls_until_completed(requests_mock):
    """Status transitions: pending → in_progress → completed; sleep is patched to avoid delays."""
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(
        f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}",
        [
            {"json": make_agent_run("pending")},
            {"json": make_agent_run("in_progress")},
            {"json": make_agent_run("completed")},
        ],
    )

    with patch("sekoiaio.elevate.execute_custom_agent.sleep") as mock_sleep:
        result = action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert result["status"] == "completed"
    run_polls = [r for r in requests_mock.request_history if r.url == f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}"]
    assert len(run_polls) == 3
    assert mock_sleep.call_count >= 2


def test_execute_custom_agent_run_in_error(requests_mock):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(
        f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}",
        [
            {"json": make_agent_run("in_progress")},
            {"json": make_agent_run("error", error="LLM quota exceeded")},
        ],
    )

    with (
        patch("sekoiaio.elevate.execute_custom_agent.sleep"),
        patch.object(action, "log") as mock_log,
        pytest.raises(AgentExecutionError),
    ):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert any("LLM quota exceeded" in str(call) for call in mock_log.call_args_list)


@pytest.mark.parametrize("status", ["out_of_quota", "rate_limited", "cancelled"])
def test_execute_custom_agent_run_failure_statuses(requests_mock, status):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(
        f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}",
        [
            {"json": make_agent_run("in_progress")},
            {"json": make_agent_run(status)},
        ],
    )

    with (
        patch("sekoiaio.elevate.execute_custom_agent.sleep"),
        patch.object(action, "log") as mock_log,
        pytest.raises(AgentExecutionError),
    ):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["level"] == "error"
    assert mock_log.call_args.kwargs["run_uuid"] == AGENT_RUN_UUID


def test_execute_custom_agent_run_unexpected_status(requests_mock):
    """A terminal status other than completed must not be reported as a success."""
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("timeout"))

    with (
        patch("sekoiaio.elevate.execute_custom_agent.sleep"),
        patch.object(action, "log") as mock_log,
        pytest.raises(AgentExecutionError, match="unexpected status: timeout"),
    ):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    mock_log.assert_called_once()


def test_execute_custom_agent_timeout(requests_mock):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", json=make_agent_run("in_progress"))

    # time() is called once to start the wait, then once per poll: jump past the 1200s timeout
    with (
        patch("sekoiaio.elevate.execute_custom_agent.sleep"),
        patch("sekoiaio.elevate.execute_custom_agent.time", side_effect=[0, 10, 5000, 5000, 5000]),
        pytest.raises(TimeoutError),
    ):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})


# ---------------------------------------------------------------------------
# run() — HTTP errors
# ---------------------------------------------------------------------------


def test_execute_custom_agent_agent_not_found(requests_mock):
    action = make_action()
    requests_mock.get(f"{AGENTS_URL}/{SAMPLE_AGENT['uuid']}", status_code=404, text="Not found")

    with patch.object(action, "log") as mock_log, pytest.raises(HTTPError):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert not any(r.method == "POST" for r in requests_mock.request_history)
    mock_log.assert_called()
    assert mock_log.call_args.kwargs["level"] == "error"


def test_execute_custom_agent_run_creation_fails(requests_mock):
    action = make_action()
    requests_mock.get(f"{AGENTS_URL}/{SAMPLE_AGENT['uuid']}", json=SAMPLE_AGENT)
    requests_mock.post(AGENT_RUNS_URL, status_code=403, text="Forbidden")

    with patch.object(action, "log") as mock_log, pytest.raises(HTTPError):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    mock_log.assert_called()
    assert mock_log.call_args.kwargs["level"] == "error"


def test_execute_custom_agent_run_creation_timeout_is_not_retried(requests_mock):
    """A timed-out POST may have created a run server-side: retrying it would start a duplicate run."""
    action = make_action()
    requests_mock.get(f"{AGENTS_URL}/{SAMPLE_AGENT['uuid']}", json=SAMPLE_AGENT)
    requests_mock.post(AGENT_RUNS_URL, exc=ReadTimeout)

    with pytest.raises(ReadTimeout):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    assert len([r for r in requests_mock.request_history if r.method == "POST"]) == 1


def test_execute_custom_agent_run_polling_fails(requests_mock):
    action = make_action()
    mock_agent_and_run_creation(requests_mock)
    requests_mock.get(f"{AGENT_RUNS_URL}/{AGENT_RUN_UUID}", status_code=400, text="Bad request")

    with (
        patch("sekoiaio.elevate.execute_custom_agent.sleep"),
        patch.object(action, "log") as mock_log,
        pytest.raises(HTTPError),
    ):
        action.run({"agent_uuid": SAMPLE_AGENT["uuid"]})

    mock_log.assert_called()
    assert mock_log.call_args.kwargs["level"] == "error"
