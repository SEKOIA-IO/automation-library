import json
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from sekoia_automation.exceptions import SendEventError

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import RETRY_TOTAL
from polyswarm_modules.trigger_polyswarm_sandbox_completed import (
    IN_FLIGHT_MAX_AGE_SECONDS,
    MAX_BACKOFF_SECONDS,
    TASK_LIST_TIMEOUT,
    SandboxCompleted,
    SandboxCompletedConfiguration,
    SandboxCompletedEvent,
)
from tests.helpers import autospec_api, autospec_request

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
    trigger.log = create_autospec(trigger.log)
    trigger.log_exception = create_autospec(trigger.log_exception)
    trigger.send_event = create_autospec(trigger.send_event)
    trigger._wait = create_autospec(trigger._wait)
    # A fresh store makes the first poll record finished tasks without emitting
    # them. Most tests are about steady state, so they start past that poll.
    trigger._mark_initialised()
    return trigger


def _with_tasks(trigger: SandboxCompleted, *tasks: MagicMock) -> MagicMock:
    """Point the trigger at a mocked PolyswarmAPI returning the given tasks."""
    api = autospec_api()
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
    first.log = create_autospec(first.log)
    first.send_event = create_autospec(first.send_event)
    first._mark_initialised()
    _with_tasks(first, task)
    assert first.poll_once() == 1

    # A fresh instance over the same data path stands in for a restart.
    second = SandboxCompleted(module=module, data_path=Path(data_storage))
    second.configuration = {"frequency": 10}
    second.log = create_autospec(second.log)
    second.send_event = create_autospec(second.send_event)
    _with_tasks(second, task)

    assert second.poll_once() == 0
    second.send_event.assert_not_called()


def test_api_error_backs_off_instead_of_crashing(trigger: SandboxCompleted) -> None:
    api = _with_tasks(trigger)
    api.sandbox_my_tasks_list.side_effect = ps_exceptions.NoResultsException(autospec_request(), "boom")

    # One pass of the loop: running is True, then the stop event ends it.
    with patch.object(SandboxCompleted, "running", new=property(lambda self: self._consecutive_failures == 0)):
        trigger.run()

    assert trigger._consecutive_failures == 1
    trigger.send_event.assert_not_called()
    # frequency 10, first failure, so the wait is 10 * 2 ** 1.
    assert trigger._wait.call_args.args[0] == 20


def test_back_off_grows_and_is_capped(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 100}
    error = ps_exceptions.RequestException(autospec_request(), "rate limited")

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
        autospec_request(), f"Authorization: {apikey} was rejected"
    )

    with patch.object(SandboxCompleted, "running", new=property(lambda self: self._consecutive_failures == 0)):
        trigger.run()

    logged = " ".join(str(call) for call in trigger.log.call_args_list)
    assert apikey not in logged
    assert "[REDACTED]" in logged


def test_the_client_is_built_from_the_module_configuration(trigger: SandboxCompleted) -> None:
    # The client is built through the shared factory in polyswarm_modules.client,
    # so PolyswarmAPI is patched where that factory actually calls it, not here.
    with patch("polyswarm_modules.client.PolyswarmAPI", autospec=True) as polyswarm_api:
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


def _fresh_trigger(module: PolyswarmModule, data_storage: str) -> SandboxCompleted:
    """A trigger over an empty store, which is what a restart that lost its state looks like."""
    fresh = SandboxCompleted(module=module, data_path=Path(data_storage))
    fresh.configuration = {"frequency": 10}
    fresh.log = create_autospec(fresh.log)
    fresh.send_event = create_autospec(fresh.send_event)
    return fresh


def test_a_task_that_leaves_the_page_while_running_is_still_emitted(trigger: SandboxCompleted) -> None:
    """A detonation outlasting ten newer submissions must not be lost.

    The listing only shows the newest ten, so the task has to be followed by
    its own identifier once it is no longer on the page.
    """
    slow = _make_sandbox_task(task_id="slow", status="RUNNING", report=None)
    api = _with_tasks(trigger, slow)
    assert trigger.poll_once() == 0

    # Ten newer tasks push it off the page, and it is still running.
    newer = [_make_sandbox_task(task_id=f"new{i}", status="RUNNING", report=None) for i in range(10)]
    api = _with_tasks(trigger, *newer)
    api.sandbox_task_status.return_value = _make_sandbox_task(task_id="slow", status="RUNNING", report=None)
    assert trigger.poll_once() == 0
    api.sandbox_task_status.assert_any_call("slow")

    # It finishes after leaving the page, and the lookup by identifier finds it.
    api = _with_tasks(trigger, *newer)
    api.sandbox_task_status.side_effect = lambda task_id: _make_sandbox_task(task_id=task_id, status="SUCCEEDED")

    assert trigger.poll_once() == 1
    assert trigger.send_event.call_args.args[1]["sandbox_task_id"] == "slow"
    assert "slow" not in trigger._in_flight()

    # And it is not emitted again.
    _with_tasks(trigger, *newer)
    assert trigger.poll_once() == 0
    assert trigger.send_event.call_count == 1


def test_a_task_still_on_the_page_is_not_looked_up_by_identifier(trigger: SandboxCompleted) -> None:
    api = _with_tasks(trigger, _make_sandbox_task(task_id="1", status="RUNNING", report=None))
    trigger.poll_once()

    api = _with_tasks(trigger, _make_sandbox_task(task_id="1", status="SUCCEEDED"))

    assert trigger.poll_once() == 1
    api.sandbox_task_status.assert_not_called()


def test_in_flight_tasks_survive_a_restart_that_keeps_the_store(data_storage: str, module: PolyswarmModule) -> None:
    first = _fresh_trigger(module, data_storage)
    first._mark_initialised()
    _with_tasks(first, _make_sandbox_task(task_id="slow", status="RUNNING", report=None))
    first.poll_once()

    second = _fresh_trigger(module, data_storage)
    api = _with_tasks(second)
    api.sandbox_task_status.return_value = _make_sandbox_task(task_id="slow", status="SUCCEEDED")

    assert second.poll_once() == 1


def test_max_tasks_per_cycle_bounds_the_lookups_and_rotates(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 10, "max_tasks_per_cycle": 2}
    running = [_make_sandbox_task(task_id=str(i), status="RUNNING", report=None) for i in range(4)]
    _with_tasks(trigger, *running)
    trigger.poll_once()

    api = _with_tasks(trigger)
    api.sandbox_task_status.side_effect = lambda task_id: _make_sandbox_task(task_id=task_id, status="RUNNING")

    trigger.poll_once()
    first_cycle = [call.args[0] for call in api.sandbox_task_status.call_args_list]
    api.sandbox_task_status.reset_mock()
    trigger.poll_once()
    second_cycle = [call.args[0] for call in api.sandbox_task_status.call_args_list]

    assert len(first_cycle) == 2
    assert len(second_cycle) == 2
    assert set(first_cycle).isdisjoint(second_cycle)


def test_a_task_that_never_finishes_is_eventually_dropped(trigger: SandboxCompleted) -> None:
    _with_tasks(trigger, _make_sandbox_task(task_id="stuck", status="RUNNING", report=None))
    trigger.poll_once()
    assert "stuck" in trigger._in_flight()

    api = _with_tasks(trigger)
    with patch.object(SandboxCompleted, "_now", return_value=trigger._now() + IN_FLIGHT_MAX_AGE_SECONDS + 1):
        trigger.poll_once()

    assert trigger._in_flight() == {}
    api.sandbox_task_status.assert_not_called()
    trigger.send_event.assert_not_called()


def test_a_task_polyswarm_no_longer_knows_is_dropped(trigger: SandboxCompleted) -> None:
    _with_tasks(trigger, _make_sandbox_task(task_id="gone", status="RUNNING", report=None))
    trigger.poll_once()

    api = _with_tasks(trigger)
    api.sandbox_task_status.side_effect = ps_exceptions.NotFoundException(autospec_request(), "no such task")
    assert trigger.poll_once() == 0

    assert trigger._in_flight() == {}


def test_a_lookup_error_propagates_but_rotates_the_task_to_the_back(trigger: SandboxCompleted) -> None:
    _with_tasks(
        trigger,
        _make_sandbox_task(task_id="a", status="RUNNING", report=None),
        _make_sandbox_task(task_id="b", status="RUNNING", report=None),
    )
    trigger.poll_once()

    api = _with_tasks(trigger)
    api.sandbox_task_status.side_effect = ps_exceptions.RequestException(autospec_request(), "server error")
    with pytest.raises(ps_exceptions.RequestException):
        trigger.poll_once()
    failed_first = api.sandbox_task_status.call_args.args[0]

    api.sandbox_task_status.reset_mock()
    with pytest.raises(ps_exceptions.RequestException):
        trigger.poll_once()

    assert api.sandbox_task_status.call_args.args[0] != failed_first


def test_a_filtered_out_running_task_is_not_followed(trigger: SandboxCompleted) -> None:
    trigger.configuration = {"frequency": 10, "sandbox": "triage"}
    _with_tasks(trigger, _make_sandbox_task(sandbox="cape", status="RUNNING", report=None))

    trigger.poll_once()

    assert trigger._in_flight() == {}


def test_first_run_records_finished_tasks_without_emitting_them(data_storage: str, module: PolyswarmModule) -> None:
    fresh = _fresh_trigger(module, data_storage)
    old = [_make_sandbox_task(task_id=str(i)) for i in range(3)]
    running = _make_sandbox_task(task_id="running", status="RUNNING", report=None)
    _with_tasks(fresh, running, *old)

    assert fresh.poll_once() == 0
    fresh.send_event.assert_not_called()

    # The next poll over the same page still emits nothing for them.
    _with_tasks(fresh, running, *old)
    assert fresh.poll_once() == 0

    # A task that was running at first sight is reported when it finishes.
    _with_tasks(fresh, _make_sandbox_task(task_id="running", status="SUCCEEDED"), *old)
    assert fresh.poll_once() == 1
    assert fresh.send_event.call_args.args[1]["sandbox_task_id"] == "running"


def test_first_run_is_safe_under_repeated_restarts_that_lose_the_store(module: PolyswarmModule) -> None:
    """Every restart that loses state must be silent, not a fresh burst of playbook runs."""
    old = [_make_sandbox_task(task_id=str(i)) for i in range(10)]
    for _ in range(3):
        with patch("sekoia_automation.constants.DATA_STORAGE", new=mkdtemp()) as storage:
            fresh = _fresh_trigger(module, storage)
            _with_tasks(fresh, *old)
            assert fresh.poll_once() == 0
            fresh.send_event.assert_not_called()
            rmtree(storage)


def test_a_failed_first_poll_is_still_a_first_poll(data_storage: str, module: PolyswarmModule) -> None:
    fresh = _fresh_trigger(module, data_storage)
    api = _with_tasks(fresh)
    api.sandbox_my_tasks_list.side_effect = ps_exceptions.RequestException(autospec_request(), "timeout")
    with pytest.raises(ps_exceptions.RequestException):
        fresh.poll_once()

    _with_tasks(fresh, _make_sandbox_task())
    assert fresh.poll_once() == 0
    fresh.send_event.assert_not_called()


def test_a_store_from_before_the_first_run_flag_is_not_treated_as_empty(
    data_storage: str, module: PolyswarmModule
) -> None:
    """An upgrade must keep reporting new completions rather than skip one poll."""
    old_store = _fresh_trigger(module, data_storage)
    old_store._remember("already-sent")

    upgraded = _fresh_trigger(module, data_storage)
    _with_tasks(upgraded, _make_sandbox_task(task_id="fresh"))

    assert upgraded.poll_once() == 1


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    return "string"


def test_an_event_with_none_fields_matches_the_results_schema(trigger: SandboxCompleted) -> None:
    """The model lets several fields be None, so the schema has to admit null for them."""
    task = _make_sandbox_task(community="", instance_id="")
    task.instance_id = None
    task.created = None
    task.expiration = None
    task.community = None
    _with_tasks(trigger, task)
    trigger.module.configuration.community = ""

    trigger.poll_once()
    _, event = trigger.send_event.call_args.args

    assert event["instance_id"] is None
    assert event["portal_url"] is None
    schema = json.loads(Path("trigger_sandbox_completed.json").read_text())["results"]
    for name, value in event.items():
        declared = schema["properties"][name]["type"]
        allowed = declared if isinstance(declared, list) else [declared]
        assert _json_type(value) in allowed, f"{name}={value!r} is not allowed by {allowed}"
    for name in schema["required"]:
        assert event[name] is not None


def test_every_nullable_event_field_is_declared_nullable() -> None:
    schema = json.loads(Path("trigger_sandbox_completed.json").read_text())["results"]
    for name, field in SandboxCompletedEvent.model_fields.items():
        declared = schema["properties"][name]["type"]
        allowed = declared if isinstance(declared, list) else [declared]
        assert ("null" in allowed) == (not field.is_required() and field.default is None), name


def test_lookups_stop_once_they_have_spent_their_share_of_the_poll_interval(
    trigger: SandboxCompleted,
) -> None:
    """A slow lookup endpoint must delay a completion, not stall the trigger.

    The budget is half the poll frequency, so with a frequency of ten seconds
    and a lookup that takes three, only the first two fit. The rest are least
    recently checked by then, so they are first in line on the next poll.
    """
    trigger.configuration = {"frequency": 10, "max_tasks_per_cycle": 4}
    clock = [1_000_000.0]

    def slow_lookup(task_id: str) -> MagicMock:
        clock[0] += 3.0
        return _make_sandbox_task(task_id=task_id, status="RUNNING")

    # The whole test runs on the fake clock, including the poll that starts the
    # four tasks off, so every stored timestamp is on the same scale.
    with patch.object(SandboxCompleted, "_now", staticmethod(lambda: clock[0])):
        running = [_make_sandbox_task(task_id=str(i), status="RUNNING", report=None) for i in range(4)]
        _with_tasks(trigger, *running)
        trigger.poll_once()

        # A poll later, so the tasks checked in the next poll are recorded as
        # checked after the ones that are not, as they would be in real time.
        clock[0] += 60.0

        api = _with_tasks(trigger)
        api.sandbox_task_status.side_effect = slow_lookup

        trigger.poll_once()
        first_cycle = [call.args[0] for call in api.sandbox_task_status.call_args_list]
        api.sandbox_task_status.reset_mock()
        trigger.poll_once()
        second_cycle = [call.args[0] for call in api.sandbox_task_status.call_args_list]

    assert len(first_cycle) == 2
    assert len(second_cycle) == 2
    assert set(first_cycle).isdisjoint(second_cycle)


def test_one_task_is_always_looked_up_even_when_the_budget_is_tiny(trigger: SandboxCompleted) -> None:
    """A frequency shorter than a single lookup must still make progress."""
    trigger.configuration = {"frequency": 10, "max_tasks_per_cycle": 4}
    _with_tasks(trigger, _make_sandbox_task(task_id="slow", status="RUNNING", report=None))
    trigger.poll_once()

    clock = [1_000_000.0]

    def very_slow_lookup(task_id: str) -> MagicMock:
        clock[0] += 600.0
        return _make_sandbox_task(task_id=task_id, status="SUCCEEDED")

    api = _with_tasks(trigger)
    api.sandbox_task_status.side_effect = very_slow_lookup

    with patch.object(SandboxCompleted, "_now", staticmethod(lambda: clock[0])):
        assert trigger.poll_once() == 1

    assert api.sandbox_task_status.call_count == 1


def test_the_first_poll_says_why_it_emitted_nothing(data_storage: str, module: PolyswarmModule) -> None:
    """A silent first poll is indistinguishable from a trigger that does not work.

    The first poll deliberately emits nothing, so it has to say so. An operator
    who has just deployed this and sees only "started" has no way to tell a
    working trigger from a broken one, and will open a ticket rather than wait.
    """
    fresh = SandboxCompleted(module=module, data_path=Path(data_storage))
    fresh.configuration = {"frequency": 10}
    fresh.log = MagicMock()
    fresh.log_exception = MagicMock()
    fresh.send_event = MagicMock()
    fresh._wait = MagicMock()
    _with_tasks(
        fresh,
        _make_sandbox_task(task_id="done", status="SUCCEEDED"),
        _make_sandbox_task(task_id="running", status="RUNNING", report=None),
    )

    assert fresh.poll_once() == 0
    fresh.send_event.assert_not_called()

    said = [str(call.args[0]) for call in fresh.log.call_args_list if call.args]

    assert any("First poll" in message for message in said), said
    assert any("without starting a playbook run" in message for message in said), said
