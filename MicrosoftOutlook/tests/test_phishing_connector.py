"""Exercise acknowledgement, pagination and restart behavior, not just event formatting."""

import json
import logging
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import Mock, patch

import pytest
import requests
from sekoia_automation.connector import Connector

from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.connector_phishing_reports import IntakeDeliveryError, PhishingReportsConnector


@pytest.fixture
def connector(tmp_path):
    module = MicrosoftOutlookModule()
    module.configuration = {"tenant_id": "tenant", "client_id": "id", "client_secret": "fake"}
    connector = PhishingReportsConnector(module=module, data_path=tmp_path)
    connector.configuration = {"intake_key": "test", "user": "report@example.com"}
    graph = Mock()
    graph.user_path.return_value = "https://graph.microsoft.com/v1.0/users/report@example.com"
    graph.folder.return_value = {"id": "inbox", "displayName": "Inbox"}
    graph.attachments.return_value = []
    graph.page.return_value = {"value": []}
    connector.__dict__["graph"] = graph
    connector.save_checkpoint({"cursor": "2026-11-10T08:00:00+00:00", "seen_ids": [], "next_link": None})
    return connector


def message(identifier="one", received="2026-11-10T08:01:00Z"):
    return {"id": identifier, "receivedDateTime": received, "subject": "Test"}


@pytest.mark.parametrize("failure_stage", ["graph", "intake"])
def test_first_failure_retains_initial_window_across_restart(connector, failure_stage):
    connector.checkpoint_path.unlink()
    start = datetime(2026, 11, 11, 8, tzinfo=UTC)
    connector.graph.page.return_value = {"value": [message()]}
    if failure_stage == "graph":
        connector.graph.page.side_effect = requests.Timeout()
    with patch("microsoft_outlook_modules.connector_phishing_reports.datetime") as clock:
        clock.now.return_value = start
        clock.fromisoformat.side_effect = datetime.fromisoformat
        with patch.object(Connector, "push_events_to_intakes", return_value=[]):
            with pytest.raises((requests.Timeout, RuntimeError)):
                connector.next_run()
        initial = connector.checkpoint_path.read_text()
        clock.now.return_value = start + timedelta(hours=2)
        restarted = PhishingReportsConnector(module=connector.module, data_path=connector.data_path)
        restarted.configuration = connector.configuration
        assert restarted.load_checkpoint()["cursor"] == "2026-11-10T08:00:00+00:00"
        assert connector.checkpoint_path.read_text() == initial


@pytest.mark.parametrize(
    "failure", ["timeout", "throttled", "service", "retries", "chunked", "decoding", "oauth429", "oauth503"]
)
def test_transient_attachment_failure_is_retried_before_checkpoint_and_mark_read(connector, sample_eml_b64, failure):
    import base64

    connector.configuration.mark_as_read = True
    connector.graph.page.return_value = {"value": [message()]}
    connector.graph.attachments.return_value = [{"id": "a", "name": "original.eml"}]
    if failure == "timeout":
        error = requests.Timeout()
    elif failure == "retries":
        error = requests.exceptions.RetryError()
    elif failure == "chunked":
        error = requests.exceptions.ChunkedEncodingError()
    elif failure == "decoding":
        error = requests.exceptions.ContentDecodingError()
    else:
        response = requests.Response()
        response.status_code = 429 if failure in {"throttled", "oauth429"} else 503
        if failure.startswith("oauth"):
            response.url = "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
        error = requests.HTTPError(response=response)
    connector.graph.attachment_bytes.side_effect = [error, base64.b64decode(sample_eml_b64)]
    initial = connector.checkpoint_path.read_text()
    with patch.object(Connector, "push_events_to_intakes", side_effect=lambda events, **_: ["ack"] * len(events)):
        with pytest.raises(type(error)):
            connector.next_run()
        assert connector.checkpoint_path.read_text() == initial
        connector.graph.json.assert_not_called()
        connector.next_run()
    assert connector.load_checkpoint()["seen_ids"] == ["one"]
    assert connector.graph.attachment_bytes.call_count == 2
    connector.graph.json.assert_called_once()


def test_terminal_attachment_failure_does_not_block_following_reports(connector):
    connector.graph.page.return_value = {"value": [message(), message("two")]}
    connector.graph.attachments.return_value = [{"id": "a", "name": "broken.eml"}]
    connector.graph.attachment_bytes.return_value = b"not an email"
    with patch.object(Connector, "push_events_to_intakes", return_value=["ack1", "ack2"]):
        connector.next_run()
    assert connector.load_checkpoint()["seen_ids"] == ["one", "two"]


def test_abandoned_batch_does_not_advance_checkpoint_or_mark_read(connector):
    connector.configuration.mark_as_read = True
    initial = connector.checkpoint_path.read_text()
    connector.graph.page.return_value = {"value": [message()]}
    iterator = connector.iterate()
    events, timestamp = next(iterator)
    assert len(events) == 1
    assert timestamp.isoformat() == "2026-11-10T08:01:00"
    assert connector.checkpoint_path.read_text() == initial
    iterator.close()  # e.g. upload raised or process stopped before acknowledgement.
    assert connector.checkpoint_path.read_text() == initial
    connector.graph.json.assert_not_called()


def test_successful_batch_persists_continuation_after_yield(connector):
    next_link = "https://graph.microsoft.com/v1.0/users/u/messages?$skiptoken=one"
    connector.graph.page.return_value = {"value": [message()], "@odata.nextLink": next_link}
    assert len(list(connector.iterate())) == 1
    checkpoint = connector.load_checkpoint()
    assert checkpoint["next_link"] == next_link
    assert checkpoint["seen_ids"] == ["one"]
    connector.graph.page.return_value = {"value": [message("two")], "@odata.nextLink": None}
    assert len(list(connector.iterate())) == 1
    connector.graph.page.assert_called_with(next_link, None)
    assert connector.load_checkpoint()["seen_ids"] == ["one", "two"]
    assert connector.load_checkpoint()["next_link"] is None


def test_restart_skips_seen_id_but_keeps_new_id_with_same_timestamp(connector):
    connector.graph.page.return_value = {"value": [message()]}
    list(connector.iterate())
    connector.graph.page.return_value = {"value": [message(), message("two")]}
    batches = list(connector.iterate())
    events = batches[0][0]
    assert [json.loads(event)["id"] for event in events] == ["two"]
    assert connector.load_checkpoint()["seen_ids"] == ["one", "two"]


def test_mailbox_change_uses_different_checkpoint(connector):
    initial_path = connector.checkpoint_path
    connector.configuration.user = "other@example.com"
    assert connector.checkpoint_path != initial_path
    assert not connector.checkpoint_path.exists()


def test_corrupt_checkpoint_surfaces_instead_of_resetting(connector):
    connector.checkpoint_path.write_text("not json")
    with pytest.raises(ValueError):
        list(connector.iterate())
    connector.graph.page.assert_not_called()


def test_sdk_swallowed_delivery_failure_is_detected(connector):
    with patch.object(Connector, "push_events_to_intakes", return_value=[]):
        with pytest.raises(RuntimeError, match="acknowledge"):
            connector.push_events_to_intakes(["event"])


def test_actual_next_run_keeps_checkpoint_on_missing_intake_acknowledgement(connector):
    connector.graph.page.return_value = {"value": [message()]}
    initial = connector.checkpoint_path.read_text()
    with patch.object(Connector, "push_events_to_intakes", return_value=[]):
        with pytest.raises(RuntimeError, match="acknowledge"):
            connector.next_run()
    assert connector.checkpoint_path.read_text() == initial


def test_mark_read_happens_only_after_batch_is_resumed(connector):
    connector.configuration.mark_as_read = True
    connector.graph.page.return_value = {"value": [message()]}
    iterator = connector.iterate()
    next(iterator)
    connector.graph.json.assert_not_called()
    list(iterator)
    connector.graph.json.assert_called_once()


def test_oversized_evidence_emits_explicit_incomplete_event(connector):
    connector.graph.page.return_value = {"value": [message() | {"body": {"content": "x" * 260000}}]}
    result = json.loads(next(connector.iterate())[0][0])
    assert result["content_truncated"] is True
    assert result["id"] == "one"
    assert result["processing_errors"]
    assert "body_content" not in result


def test_stop_does_not_checkpoint_an_unprocessed_page(connector):
    connector.graph.page.return_value = {"value": [message()]}
    initial = connector.checkpoint_path.read_text()
    connector._stop_event.set()
    assert list(connector.iterate()) == []
    assert connector.checkpoint_path.read_text() == initial


def test_poll_wait_is_interruptible(connector):
    connector.next_run = Mock(side_effect=lambda: connector._stop_event.set())
    connector.heartbeat = Mock()
    connector.run()
    connector.next_run.assert_called_once()
    assert isinstance(connector._stop_event, Event)


def test_late_visible_message_within_overlap_is_collected_once(connector):
    connector.graph.page.return_value = {"value": [message()]}
    list(connector.iterate())
    connector.graph.page.return_value = {"value": [message("late", "2026-11-10T08:00:30Z"), message()]}
    batches = list(connector.iterate())
    events = batches[0][0]
    assert [json.loads(event)["id"] for event in events] == ["late"]
    assert connector.load_checkpoint()["cursor"] == "2026-11-10T08:01:00+00:00"
    assert list(connector.iterate()) == []


def test_expired_continuation_restarts_from_acknowledged_cursor(connector):
    state = connector.load_checkpoint() | {"next_link": "https://graph.microsoft.com/v1.0/expired"}
    connector.save_checkpoint(state)
    response = Mock(status_code=410)
    from requests import HTTPError

    connector.graph.page.side_effect = HTTPError(response=response)
    with pytest.raises(HTTPError):
        list(connector.iterate())
    assert connector.load_checkpoint()["next_link"] is None
    assert connector.load_checkpoint()["cursor"] == state["cursor"]


@pytest.mark.parametrize("has_more,failed,expected_delay", [(False, False, 60), (True, False, 0), (True, True, 60)])
def test_run_reports_progress_and_waits_interruptibly(connector, caplog, has_more, failed, expected_delay):
    caplog.set_level(logging.INFO)
    connector.log = Mock()
    connector.log_exception = Mock()
    connector._has_more = has_more
    connector.next_run = Mock(side_effect=RuntimeError("Collection failed") if failed else None)
    connector.heartbeat = Mock()
    stop_event = connector._stop_event
    with patch.object(stop_event, "wait", side_effect=lambda _: stop_event.set()) as wait:
        connector.run()
    wait.assert_called_once_with(expected_delay)
    messages = [call.kwargs["message"] for call in connector.log.call_args_list]
    assert any(message.startswith("Starting phishing report connector") for message in messages)
    assert any("Duration:" in message for message in messages)
    assert "Phishing report connector stopped" in messages
    runtime_messages = [record.getMessage() for record in caplog.records]
    assert "Starting phishing report collection cycle" in runtime_messages
    assert "Starting phishing report collection cycle" not in messages
    if failed:
        connector.log_exception.assert_called_once()
        assert not any(message.startswith("Collection cycle completed") for message in runtime_messages)
    else:
        assert any(message.startswith("Collection cycle completed") for message in runtime_messages)
    if expected_delay:
        assert "Next batch in the future. Waiting 60 seconds" in runtime_messages
    else:
        assert "More pages available. Fetching next batch immediately" in runtime_messages


def test_logs_distinguish_empty_cycle_from_successfully_acknowledged_batch(connector, caplog):
    caplog.set_level(logging.INFO)
    connector.log = Mock()
    assert list(connector.iterate()) == []
    messages = [record.getMessage() for record in caplog.records]
    assert "Fetched 0 messages from Microsoft Graph" in messages
    assert "No new emails found" in messages
    assert not any("acknowledged" in message for message in messages)

    connector.log.reset_mock()
    caplog.clear()
    connector.graph.page.return_value = {"value": [message()]}
    connector.put_forward_events_duration = Mock()
    connector.put_forwarded_events = Mock()
    connector.put_events_lag = Mock()
    with patch.object(Connector, "push_events_to_intakes", return_value=["event-id"]):
        connector.next_run()
    messages = [record.getMessage() for record in caplog.records]
    forwarded = messages.index("Forwarding 1 email events to intake")
    acknowledged = messages.index("Intake acknowledged 1 events")
    saved = messages.index("Checkpoint saved; more pages: False")
    assert forwarded < acknowledged < saved
    connector.log.assert_not_called()
    assert connector._activity["events"] == 1


def test_failed_upload_never_logs_acknowledgement_or_saved_checkpoint(connector, caplog):
    caplog.set_level(logging.INFO)
    connector.log = Mock()
    connector.graph.page.return_value = {"value": [message()]}
    with patch.object(Connector, "push_events_to_intakes", return_value=[]):
        with pytest.raises(RuntimeError, match="acknowledge"):
            connector.next_run()
    messages = [record.getMessage() for record in caplog.records]
    assert "Forwarding 1 email events to intake" in messages
    assert not any("acknowledged" in message or "Checkpoint saved" in message for message in messages)
    assert connector._activity["events"] == 0
    assert connector._activity["submissions"] == 0
    assert connector._activity["originals"] == 0


def test_summary_counts_submissions_originals_and_actual_event_extraction_outcomes(connector):
    connector.graph.page.return_value = {"value": [message(str(i)) for i in range(4)]}
    originals = [{"source_attachment_id": "a"}, {"source_attachment_id": "b"}]
    with (
        patch(
            "microsoft_outlook_modules.connector_phishing_reports.collect_attachments",
            side_effect=[
                ([], originals, []),
                ([], originals[:1], [{"error": "Bad MSG"}]),
                ([], [], [{"error": "Bad MSG"}]),
                ([], [], []),
            ],
        ),
        patch.object(Connector, "push_events_to_intakes", side_effect=lambda events, **_: ["ack"] * len(events)),
    ):
        connector.next_run()
    assert connector._activity["submissions"] == 4
    assert connector._activity["originals"] == 3
    assert connector._activity["complete"] == 2
    assert connector._activity["partial"] == 1
    assert connector._activity["failed"] == 1
    assert connector._activity["no_embedded_email"] == 1
    assert connector._activity["events"] == 5
    before = connector._activity.copy()
    connector.next_run()  # Overlap fetches previously seen messages, not new submissions.
    assert connector._activity == before


def test_abandoned_page_does_not_count_prepared_submissions(connector):
    connector.graph.page.return_value = {"value": [message()]}
    iterator = connector.iterate()
    next(iterator)
    iterator.close()
    assert connector._activity["submissions"] == 0
    assert connector._activity["no_embedded_email"] == 0


def test_checkpoint_failure_keeps_processed_counts_separate_from_accepted_events(connector):
    connector.graph.page.return_value = {"value": [message()]}
    with (
        patch.object(Connector, "push_events_to_intakes", return_value=["ack"]),
        patch.object(connector, "save_checkpoint", side_effect=OSError("Storage unavailable")),
    ):
        with pytest.raises(OSError):
            connector.next_run()
    assert connector._activity["events"] == 1
    assert connector._activity["submissions"] == 0


@pytest.mark.parametrize("failed", [False, True])
def test_empty_summary_does_not_claim_no_new_submissions_on_failure(connector, failed):
    connector.log = Mock()
    connector._activity.update(cycles=1, failures=int(failed))
    connector._report_activity(3.17, 60)
    summary = connector.log.call_args.kwargs["message"]
    assert ("No new submissions" in summary) is not failed
    assert "Duration: 3.2 seconds" in summary
    assert "Next batch in 60 seconds" in summary
    assert "cycle" not in summary


def test_stopping_summary_retains_last_duration_and_does_not_schedule_another_poll(connector):
    connector.log = Mock()
    connector._activity.update(cycles=1, events=1)
    connector._stop_event.set()
    connector._report_activity(3.17, 0)
    summary = connector.log.call_args.kwargs["message"]
    assert "Duration: 3.2 seconds" in summary
    assert "Connector stopping" in summary
    assert "Next batch" not in summary


def test_shutdown_does_not_duplicate_the_completed_run_log(connector):
    connector.log = Mock()
    connector.heartbeat = Mock()
    clock = [0.0]

    def collect():
        clock[0] += 3.17

    connector.next_run = Mock(side_effect=collect)
    with (
        patch("microsoft_outlook_modules.connector_phishing_reports.monotonic", side_effect=lambda: clock[0]),
        patch.object(connector._stop_event, "wait", side_effect=lambda _: connector._stop_event.set()),
    ):
        connector.run()
    summaries = [c.kwargs["message"] for c in connector.log.call_args_list if "Duration:" in c.kwargs["message"]]
    assert len(summaries) == 1
    assert "Duration: 3.2 seconds" in summaries[0]
    assert "Next batch in 60 seconds" in summaries[0]


@pytest.mark.parametrize(
    "activity,expected",
    [
        ({"cycles": 1}, "No new submissions. Duration: 7.8 seconds. Next batch in 60 seconds."),
        (
            {"cycles": 1, "submissions": 1, "originals": 1, "complete": 1, "events": 1},
            "1 submission processed. Extraction outcomes: 1 complete, 0 partial, 0 failed. "
            "Duration: 7.8 seconds. Next batch in 60 seconds.",
        ),
        (
            {"cycles": 1, "submissions": 1, "originals": 2, "complete": 1, "partial": 1, "events": 2},
            "1 submission processed. Extraction outcomes: 1 complete, 1 partial, 0 failed. "
            "Duration: 7.8 seconds. Next batch in 60 seconds.",
        ),
    ],
)
def test_compact_success_messages_keep_multiple_original_support(connector, activity, expected):
    connector.log = Mock()
    connector._activity.update(activity)
    connector._report_activity(7.8, 60)
    assert connector.log.call_args.kwargs == {"message": expected, "level": "info"}


def test_missing_original_is_visible_only_when_present(connector):
    connector.log = Mock()
    connector._activity.update(cycles=1, submissions=1, no_embedded_email=1, events=1)
    connector._report_activity(2.32, 60)
    summary = connector.log.call_args.kwargs["message"]
    assert "1 without embedded email." in summary
    assert "Duration: 2.3 seconds." in summary


def test_intake_failure_has_distinct_message_and_retains_checkpoint(connector):
    connector.graph.page.return_value = {"value": [message()]}
    initial = connector.checkpoint_path.read_text()
    connector.log = Mock()
    connector.log_exception = Mock()
    with (
        patch.object(Connector, "push_events_to_intakes", return_value=[]),
        patch.object(connector._stop_event, "wait", side_effect=lambda _: connector._stop_event.set()),
    ):
        connector.run()
    assert connector.checkpoint_path.read_text() == initial
    detail = connector.log_exception.call_args
    assert isinstance(detail.args[0], IntakeDeliveryError)
    assert detail.kwargs["message"] == "Failed to deliver events to intake; checkpoint unchanged"
    summaries = [c for c in connector.log.call_args_list if "Duration:" in c.kwargs["message"]]
    assert len(summaries) == 1
    assert summaries[0].kwargs["level"] == "warning"
    assert summaries[0].kwargs["message"].startswith("Intake delivery failed; checkpoint unchanged.")
    assert "No new submissions" not in summaries[0].kwargs["message"]


@pytest.mark.parametrize("interval,events_per_cycle", [(10, 0), (60, 0), (10, 2), (60, 2)])
def test_each_run_logs_once_including_idle_runs(connector, interval, events_per_cycle):
    connector.configuration.polling_interval = interval
    connector.log = Mock()
    connector.heartbeat = Mock()
    clock = [0.0]

    def collect():
        connector._activity["events"] += events_per_cycle

    def wait(delay):
        assert delay == interval
        clock[0] += delay
        if clock[0] >= 3600:
            connector._stop_event.set()

    connector.next_run = Mock(side_effect=collect)
    with (
        patch("microsoft_outlook_modules.connector_phishing_reports.monotonic", side_effect=lambda: clock[0]),
        patch.object(connector._stop_event, "wait", side_effect=wait),
    ):
        connector.run()
    logs = [c.kwargs["message"] for c in connector.log.call_args_list]
    summaries = [message for message in logs if "Duration:" in message]
    assert len(summaries) == 3600 // interval
    assert len(logs) == len(summaries) + 2  # Startup and shutdown only.
    if interval == 60:
        assert len(logs) < 100
    assert connector.next_run.call_count == 3600 // interval


def test_idle_runs_do_not_wait_five_minutes_and_counters_reset_each_time(connector):
    connector.log = Mock()
    for _ in range(3):
        connector._activity.update(cycles=1)
        connector._report_activity(2.3, 60)
        assert not any(connector._activity.values())
    assert connector.log.call_count == 3
    assert all(
        c.kwargs["message"] == "No new submissions. Duration: 2.3 seconds. Next batch in 60 seconds."
        for c in connector.log.call_args_list
    )


def test_processing_counts_belong_to_the_current_run(connector):
    connector.log = Mock()
    connector._activity.update(cycles=1, submissions=1, originals=2, complete=1, partial=1, events=2)
    connector._report_activity(3.17, 60)
    connector._activity.update(cycles=1)
    connector._report_activity(2.0, 60)
    messages = [c.kwargs["message"] for c in connector.log.call_args_list]
    assert messages[0] == (
        "1 submission processed. Extraction outcomes: 1 complete, 1 partial, 0 failed. "
        "Duration: 3.2 seconds. Next batch in 60 seconds."
    )
    assert messages[1] == "No new submissions. Duration: 2.0 seconds. Next batch in 60 seconds."
    assert not any(connector._activity.values())


def test_multiple_originals_share_one_acknowledged_report_checkpoint(connector):
    connector.configuration.mark_as_read = True
    connector.graph.page.return_value = {"value": [message()]}
    originals = [
        {"message_id": "<first@example.com>", "source_attachment_id": "one"},
        {"message_id": "<second@example.com>", "source_attachment_id": "two"},
    ]
    initial = connector.checkpoint_path.read_text()
    with patch(
        "microsoft_outlook_modules.connector_phishing_reports.collect_attachments", return_value=([], originals, [])
    ):
        iterator = connector.iterate()
        events, _ = next(iterator)
        assert len(events) == 2
        assert all(json.loads(event)["id"] == "one" for event in events)
        assert connector.checkpoint_path.read_text() == initial
        connector.graph.json.assert_not_called()

        iterator.close()
        # A partial intake acknowledgement must likewise prevent checkpointing and marking as read.
        with patch.object(Connector, "push_events_to_intakes", return_value=["only-one-ack"]):
            with pytest.raises(RuntimeError, match="acknowledge"):
                connector.next_run()
        assert connector.checkpoint_path.read_text() == initial
        connector.graph.json.assert_not_called()


def test_intake_initial_422_retries_past_three_attempts_then_acknowledges(connector, requests_mock):
    from tenacity import Retrying, stop_after_attempt, wait_exponential

    connector.configuration.intake_server = "https://intake.sekoia.io"
    connector.configuration.mark_as_read = True
    connector.graph.page.return_value = {"value": [message()]}
    connector.log = Mock()
    connector.log_exception = Mock()
    initial = connector.checkpoint_path.read_text()
    attempts = []

    def response(_request, context):
        assert connector.checkpoint_path.read_text() == initial
        connector.graph.json.assert_not_called()
        attempts.append(1)
        if len(attempts) <= 4:
            context.status_code = 422
            return {"error": "INTAKE_KEY_ERROR"}
        return {"event_ids": ["acknowledged"]}

    requests_mock.post("https://intake.sekoia.io/batch", json=response)
    standard = Retrying(stop=stop_after_attempt(5), wait=wait_exponential(max=10), reraise=True)
    with (
        patch.object(Connector, "_retry", return_value=standard),
        patch.object(connector._stop_event, "wait", return_value=False) as wait,
    ):
        connector.next_run()
    assert len(attempts) == 5
    assert [call.args[0] for call in wait.call_args_list] == [1, 2, 4, 8]
    assert connector.load_checkpoint()["seen_ids"] == ["one"]
    connector.graph.json.assert_called_once()
    connector.log_exception.assert_not_called()
    warnings = [call for call in connector.log.call_args_list if call.kwargs.get("level") == "warning"]
    assert len(warnings) == 1
    assert "HTTP 422" in warnings[0].kwargs["message"]
    assert any("delivery resumed" in call.kwargs.get("message", "") for call in connector.log.call_args_list)


def test_retry_adaptation_preserves_sdk_error_specific_waits(connector):
    from tenacity import Retrying, stop_after_attempt, wait_fixed

    # Represents the policy proposed in SDK PR 252, without depending on unreleased SDK code.
    standard = Retrying(stop=stop_after_attempt(4), wait=wait_fixed(300), reraise=True)
    with patch.object(Connector, "_retry", return_value=standard):
        policy = connector._retry()
    assert policy.wait is standard.wait
    assert policy.wait(Mock()) == 300
    connector._stop_event.set()
    assert policy.sleep(300) is True  # Stop interrupts even the proposed five-minute wait.
    assert policy.stop(Mock(attempt_number=1)) is True


def test_sdk_retry_budget_still_surfaces_persistent_delivery_failure(connector, requests_mock):
    from tenacity import Retrying, stop_after_attempt, wait_none

    connector.configuration.intake_server = "https://intake.sekoia.io"
    connector.graph.page.return_value = {"value": [message()]}
    connector.log = Mock()
    connector.log_exception = Mock()
    initial = connector.checkpoint_path.read_text()
    requests_mock.post("https://intake.sekoia.io/batch", status_code=503)
    standard = Retrying(stop=stop_after_attempt(2), wait=wait_none(), reraise=True)
    with patch.object(Connector, "_retry", return_value=standard):
        with pytest.raises(RuntimeError, match="acknowledge"):
            connector.next_run()
    assert requests_mock.call_count == 2
    assert connector.checkpoint_path.read_text() == initial
    assert connector.log_exception.called


def test_default_retry_budget_keeps_sdk_one_hour_limit(connector):
    policy = connector._retry()
    assert policy.stop(Mock(seconds_since_start=3599)) is False
    assert policy.stop(Mock(seconds_since_start=3600)) is True


def test_long_microsoft_backoff_is_preserved_and_interruptible(connector):
    from microsoft_outlook_modules.client.retry import RetryDelayExceeded

    with patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100):
        failure = RetryDelayExceeded(3600)
    connector.next_run = Mock(side_effect=failure)
    connector.log_exception = Mock()
    connector.log = Mock()
    stop_event = connector._stop_event
    with (
        patch("microsoft_outlook_modules.connector_phishing_reports.monotonic", return_value=120),
        patch.object(stop_event, "wait", side_effect=lambda _: stop_event.set()) as wait,
    ):
        connector.run()
    wait.assert_called_once_with(3580)
    connector.next_run.assert_called_once()


@pytest.mark.parametrize("has_more", [False, True])
@pytest.mark.parametrize("failure_kind", ["adapter", "http", "wrapped"])
def test_post_delivery_backoff_stops_optional_writes_and_preserves_acknowledged_page(
    connector, has_more, failure_kind
):
    from microsoft_outlook_modules.client.retry import RetryDelayExceeded

    connector.configuration.mark_as_read = True
    page = {"value": [message(), message("two")]}
    if has_more:
        page["@odata.nextLink"] = "https://graph.microsoft.com/v1.0/next"
    connector.graph.page.return_value = page
    if failure_kind in {"adapter", "wrapped"}:
        with patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100):
            failure = RetryDelayExceeded(3600)
        if failure_kind == "wrapped":
            failure = requests.ConnectionError(failure)
    else:
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "3600"
        failure = requests.HTTPError(response=response)
    connector.graph.json.side_effect = failure
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.heartbeat = Mock()
    stop = connector._stop_event
    with (
        patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100),
        patch("microsoft_outlook_modules.connector_phishing_reports.monotonic", return_value=100),
        patch.object(Connector, "push_events_to_intakes", return_value=["one", "two"]),
        patch.object(stop, "wait", side_effect=lambda _: stop.set()) as wait,
    ):
        connector.run()
    wait.assert_called_once_with(3600)
    connector.graph.json.assert_called_once()
    connector.graph.page.assert_called_once()
    state = connector.load_checkpoint()
    assert state["seen_ids"] == ["one", "two"]
    assert state["next_link"] == page.get("@odata.nextLink")
    messages = [call.kwargs.get("message", "") for call in connector.log_exception.call_args_list]
    assert messages == ["Events delivered but marking a report as read failed"]


@pytest.mark.parametrize("status", [429, 503])
def test_oauth_http_backoff_defers_collection_without_acknowledging_evidence(connector, status):
    response = requests.Response()
    response.status_code = status
    response.url = "https://login.microsoftonline.com/tenant/oauth2/v2.0/token"
    response.headers["Retry-After"] = "3600"
    connector.graph.page.return_value = {"value": [message()]}
    connector.graph.attachments.return_value = [{"id": "a", "name": "original.eml"}]
    connector.graph.attachment_bytes.side_effect = requests.HTTPError(response=response)
    connector.log = Mock()
    connector.log_exception = Mock()
    initial = connector.checkpoint_path.read_text()
    stop = connector._stop_event
    with (
        patch("microsoft_outlook_modules.client.retry.time.monotonic", return_value=100),
        patch("microsoft_outlook_modules.connector_phishing_reports.monotonic", return_value=100),
        patch.object(Connector, "push_events_to_intakes") as push,
        patch.object(stop, "wait", side_effect=lambda _: stop.set()) as wait,
    ):
        connector.run()
    wait.assert_called_once_with(3600)
    push.assert_not_called()
    assert connector.checkpoint_path.read_text() == initial
