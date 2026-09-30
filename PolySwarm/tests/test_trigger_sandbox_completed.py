import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from sekoia_automation.exceptions import SendEventError

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import RETRY_TOTAL
from polyswarm_modules.trigger_polyswarm_sandbox_completed import (
    MAX_BACKOFF_SECONDS,
    TASK_LIST_TIMEOUT,
    SandboxCompleted,
    SandboxCompletedConfiguration,
)

_DEFAULT_REPORT = object()


def _make_sandbox_task(
    *,
    task_id: str = "4242",
    sha256: str = "aa" * 32,
    sandbox: str = "cape",
    status: str = "SUCCEEDED",
    community: str = "default",
    instance_id: str = "9001",
    report: Any = _DEFAULT_REPORT,
    sandbox_artifacts: list[Any] | None = None,
) -> MagicMock:
    if report is _DEFAULT_REPORT:
        report = {"info": {"score": 8}}

    task = MagicMock()
    task.id = task_id
    task.sha256 = sha256
    task.sandbox = sandbox
    task.status = status
    task.community = community
    task.instance_id = instance_id
    task.created = "2026-09-21T10:00:00Z"
    task.expiration = "2026-10-21T10:00:00Z"
    task.report = report
    task.sandbox_artifacts = sandbox_artifacts if sandbox_artifacts is not None else [MagicMock()]
    return task


@pytest.fixture
def trigger(data_storage: str, module: PolyswarmModule) -> SandboxCompleted:
    trigger = SandboxCompleted(module=module, data_path=Path(data_storage))
    trigger.configuration = {"frequency": 10}
    # The SDK ships logs to the Sekoia API and retries on failure, which has no
    # place in a unit test. Event sending is mocked for the same reason.
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = MagicMock()
    trigger._wait = MagicMock()
    return trigger


def _with_tasks(trigger: SandboxCompleted, *tasks: MagicMock) -> MagicMock:
    """Point the trigger at a mocked PolyswarmAPI returning the given tasks."""
    api = MagicMock()
    api.uri = "https://api.polyswarm.network/v3"
    api.sandbox_my_tasks_list.return_value = iter(tasks)
    trigger.__dict__["client"] = api
    return api


def test_completed_task_emits_exactly_one_event(trigger: SandboxCompleted) -> None:
    _with_tasks(trigger, _make_sandbox_task())

    assert trigger.poll_once() == 1
    assert trigger.send_event.call_count == 1

    name, event = trigger.send_event.call_args.args
    assert name == "PolySwarm cape detonation 4242 completed"
    assert event["sandbox_task_id"] == "4242"
    assert event["sha256"] == "aa" * 32
    assert event["sandbox"] == "cape"
    assert event["status"] == "SUCCEEDED"
    assert event["report_available"] is True
    assert event["report_url"] == (
        "https://api.polyswarm.network/v3/sandbox/sandboxtask?sandbox_task_id=4242&community=default"
    )
    assert event["portal_url"] == f"https://polyswarm.network/scan/results/file/{'aa' * 32}/9001"
    assert event["sandbox_artifact_count"] == 1


def test_running_task_emits_nothing(trigger: SandboxCompleted) -> None:
    _with_tasks(trigger, _make_sandbox_task(status="RUNNING", report=None))

    assert trigger.poll_once() == 0
    trigger.send_event.assert_not_called()


def test_failed_task_is_emitted_with_its_status(trigger: SandboxCompleted) -> None:
    _with_tasks(trigger, _make_sandbox_task(status="FAILED", report=None))

    assert trigger.poll_once() == 1
    _, event = trigger.send_event.call_args.args
    assert event["status"] == "FAILED"
    assert event["report_available"] is False


def test_failed_task_is_skipped_when_emit_failed_is_off(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 10, "emit_failed": False}
    _with_tasks(trigger, _make_sandbox_task(status="FAILED", report=None))

    assert trigger.poll_once() == 0
    trigger.send_event.assert_not_called()


def test_task_from_another_sandbox_is_filtered_out(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 10, "sandbox": "triage"}
    _with_tasks(trigger, _make_sandbox_task(sandbox="cape"))

    assert trigger.poll_once() == 0
    trigger.send_event.assert_not_called()


def test_same_task_is_not_emitted_twice_across_two_cycles(trigger: SandboxCompleted) -> None:
    task = _make_sandbox_task()

    _with_tasks(trigger, task)
    assert trigger.poll_once() == 1

    # Second cycle, the same completed task is still at the top of the list.
    _with_tasks(trigger, task)
    assert trigger.poll_once() == 0

    assert trigger.send_event.call_count == 1


def test_a_send_failure_does_not_record_the_task_as_emitted(trigger: SandboxCompleted) -> None:
    """A task must only count as emitted once Sekoia has actually accepted the event.

    If send_event raises partway through a cycle, the task it was sending has
    to be retried on the next poll rather than lost, which means the store
    must not be written to before send_event returns successfully.
    """
    task = _make_sandbox_task()
    _with_tasks(trigger, task)
    trigger.send_event.side_effect = SendEventError("could not reach Sekoia")

    with pytest.raises(SendEventError):
        trigger.poll_once()

    # Nothing was recorded, so the very same task is retried on the next poll.
    trigger.send_event.side_effect = None
    trigger.send_event.reset_mock()
    _with_tasks(trigger, task)
    assert trigger.poll_once() == 1
    trigger.send_event.assert_called_once()


def test_a_send_failure_partway_through_a_cycle_only_loses_the_failed_task(trigger: SandboxCompleted) -> None:
    """Two tasks in one cycle: the one that sent successfully must not be replayed."""
    first_task = _make_sandbox_task(task_id="1")
    second_task = _make_sandbox_task(task_id="2")
    _with_tasks(trigger, first_task, second_task)
    trigger.send_event.side_effect = [None, SendEventError("could not reach Sekoia")]

    with pytest.raises(SendEventError):
        trigger.poll_once()

    trigger.send_event.side_effect = None
    trigger.send_event.reset_mock()
    _with_tasks(trigger, first_task, second_task)

    assert trigger.poll_once() == 1
    trigger.send_event.assert_called_once()
    assert trigger.send_event.call_args.args[1]["sandbox_task_id"] == "2"


def test_emitted_identifiers_survive_a_restart(data_storage: str, module: PolyswarmModule) -> None:
    task = _make_sandbox_task()

    first = SandboxCompleted(module=module, data_path=Path(data_storage))
    first.configuration = {"frequency": 10}
    first.log = MagicMock()
    first.send_event = MagicMock()
    _with_tasks(first, task)
    assert first.poll_once() == 1

    # A fresh instance over the same data path stands in for a restart.
    second = SandboxCompleted(module=module, data_path=Path(data_storage))
    second.configuration = {"frequency": 10}
    second.log = MagicMock()
    second.send_event = MagicMock()
    _with_tasks(second, task)

    assert second.poll_once() == 0
    second.send_event.assert_not_called()


def test_only_the_newest_tasks_are_examined(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 10, "max_tasks_per_cycle": 2}
    _with_tasks(
        trigger,
        _make_sandbox_task(task_id="1"),
        _make_sandbox_task(task_id="2"),
        _make_sandbox_task(task_id="3"),
    )

    assert trigger.poll_once() == 2
    emitted = [call.args[1]["sandbox_task_id"] for call in trigger.send_event.call_args_list]
    assert emitted == ["1", "2"]


def test_api_error_backs_off_instead_of_crashing(trigger: SandboxCompleted) -> None:
    api = _with_tasks(trigger)
    api.sandbox_my_tasks_list.side_effect = ps_exceptions.NoResultsException(MagicMock(), "boom")

    # One pass of the loop: running is True, then the stop event ends it.
    with patch.object(SandboxCompleted, "running", new=property(lambda self: self._consecutive_failures == 0)):
        trigger.run()

    assert trigger._consecutive_failures == 1
    trigger.send_event.assert_not_called()
    # frequency 10, first failure, so the wait is 10 * 2 ** 1.
    assert trigger._wait.call_args.args[0] == 20


def test_back_off_grows_and_is_capped(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 100}
    error = ps_exceptions.RequestException(MagicMock(), "rate limited")

    delays = []
    for _ in range(6):
        trigger._back_off("failed", error)
        delays.append(trigger._wait.call_args.args[0])

    assert delays[0] == 200
    assert delays[1] == 400
    assert delays[-1] == MAX_BACKOFF_SECONDS
    assert all(delay <= MAX_BACKOFF_SECONDS for delay in delays)


def test_a_successful_cycle_resets_the_back_off(trigger: SandboxCompleted) -> None:
    trigger._consecutive_failures = 3
    _with_tasks(trigger, _make_sandbox_task())

    with patch.object(SandboxCompleted, "running", new=property(lambda self: self._consecutive_failures == 3)):
        trigger.run()

    assert trigger._consecutive_failures == 0


def test_the_api_key_never_reaches_a_log_line_or_an_event(trigger: SandboxCompleted) -> None:
    apikey = trigger.module.configuration.apikey
    api = _with_tasks(trigger, _make_sandbox_task())
    api.sandbox_my_tasks_list.side_effect = ps_exceptions.RequestException(
        MagicMock(), f"Authorization: {apikey} was rejected"
    )

    with patch.object(SandboxCompleted, "running", new=property(lambda self: self._consecutive_failures == 0)):
        trigger.run()

    logged = " ".join(str(call) for call in trigger.log.call_args_list)
    assert apikey not in logged
    assert "[REDACTED]" in logged


def test_the_client_is_built_from_the_module_configuration(trigger: SandboxCompleted) -> None:
    # The client is built through the shared factory in polyswarm_modules.client,
    # so PolyswarmAPI is patched where that factory actually calls it, not here.
    with patch("polyswarm_modules.client.PolyswarmAPI") as polyswarm_api:
        assert trigger.client is polyswarm_api.return_value

    # The timeout is not decoration. The task listing endpoint answers in about
    # seven seconds where other calls answer in under one, so the client default
    # of thirty leaves no margin. build_client is expected to pass it through
    # rather than fall back to its own default.
    polyswarm_api.assert_called_once_with(key="test-api-key", community="default", timeout=TASK_LIST_TIMEOUT)


def test_the_client_has_retries_installed_for_safe_methods(trigger: SandboxCompleted) -> None:
    """Adopting build_client is only meaningful if the retrying adapter is actually mounted."""
    session = trigger.client.session
    for scheme in ("http://", "https://"):
        adapter = session.get_adapter(scheme)
        assert adapter.max_retries.total == RETRY_TOTAL


def test_only_one_page_is_ever_requested(trigger: SandboxCompleted) -> None:
    """A request carrying a page offset does not answer, so a second page would hang the cycle."""
    api = _with_tasks(
        trigger,
        _make_sandbox_task(task_id="1"),
        _make_sandbox_task(task_id="2"),
        _make_sandbox_task(task_id="3"),
    )
    trigger.configuration.page_size = 2
    trigger.configuration.max_tasks_per_cycle = 100

    tasks = trigger._recent_tasks()

    assert len(tasks) == 2
    api.sandbox_my_tasks_list.assert_called_once_with(limit=2)


def test_the_descriptor_matches_the_model() -> None:
    """A descriptor promising a value the model refuses is a silent rejection for the customer."""
    descriptor = json.loads(Path("trigger_sandbox_completed.json").read_text())
    properties = descriptor["arguments"]["properties"]
    fields = SandboxCompletedConfiguration.model_fields

    for name, declared in properties.items():
        field = fields[name]
        if "default" in declared:
            assert declared["default"] == field.default, f"{name} default differs"
        bounds = {type(m).__name__: getattr(m, "ge", getattr(m, "le", None)) for m in field.metadata}
        if "maximum" in declared and "Le" in bounds:
            assert declared["maximum"] == bounds["Le"], f"{name} maximum differs"
        if "minimum" in declared and "Ge" in bounds:
            assert declared["minimum"] == bounds["Ge"], f"{name} minimum differs"
