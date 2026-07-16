import json
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from flareio_modules import FlareIOModule
from flareio_modules.trigger_flare_events import FlareEventsConnector


def _build_trigger(data_storage):
    module = FlareIOModule()
    module.configuration = {
        "api_key": "fw_test_key",
        "tenant_id": 7,
    }

    trigger = FlareEventsConnector(module=module, data_path=data_storage)
    trigger.configuration = {
        "intake_key": "intake_key",
        "frequency": 60,
        "page_size": 10,
        "initial_hours_lookback": 1,
        "throttle_seconds": 0,
    }
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    return trigger


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_first_run_builds_initial_filter(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = [
        SimpleNamespace(
            event={"activity": {"header": {"uid": "evt-1", "type": "chat_message"}}},
            next="cursor-1",
        ),
        SimpleNamespace(
            event={"activity": {"header": {"uid": "evt-2", "type": "forum_post"}}},
            next="cursor-2",
        ),
    ]

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    assert trigger.cursor.offset == "cursor-2"
    assert trigger.push_events_to_intakes.called

    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed_events) == 2
    assert json.loads(pushed_events[0])["header"]["uid"] == "evt-1"

    payload = fake_client.scroll_events.call_args.kwargs["json"]
    assert payload["size"] == 10
    assert payload["order"] == "asc"
    assert payload["from"] is None
    assert "filters" in payload


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_resumes_from_checkpoint(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "previous-cursor"

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = [
        {
            "event": {"activity": {"header": {"uid": "evt-3", "type": "listing"}}},
            "next": "next-cursor",
        }
    ]

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    payload = fake_client.scroll_events.call_args.kwargs["json"]
    assert payload["from"] == "previous-cursor"
    assert "filters" not in payload
    assert trigger.cursor.offset == "next-cursor"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_no_event_keeps_cursor(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "stable-cursor"

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = [
        SimpleNamespace(event=None, next=None),
    ]

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    assert trigger.cursor.offset == "stable-cursor"
    trigger.push_events_to_intakes.assert_not_called()


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_empty_event_with_next_updates_cursor(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "cursor-before"

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = [
        SimpleNamespace(event=None, next="cursor-after"),
    ]

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    # No event to forward, but checkpoint must still progress.
    assert trigger.cursor.offset == "cursor-after"
    trigger.push_events_to_intakes.assert_not_called()


def test_requests_session_has_retry_policy(data_storage):
    trigger = _build_trigger(data_storage)

    adapter = trigger.requests_session.get_adapter("https://api.flare.io")
    retries = adapter.max_retries

    assert retries.total == 5
    assert retries.backoff_factor == 2
    assert retries.backoff_max == 15
    assert set(retries.status_forcelist) == {429, 502, 503, 504}


def test_requests_session_retries_post_on_transient_api_statuses(data_storage):
    trigger = _build_trigger(data_storage)

    adapter = trigger.requests_session.get_adapter("https://api.flare.io")
    retries = adapter.max_retries

    assert retries.is_retry("POST", 429, has_retry_after=False) is True
    assert retries.is_retry("POST", 502, has_retry_after=False) is True
    assert retries.is_retry("POST", 503, has_retry_after=False) is True
    assert retries.is_retry("POST", 504, has_retry_after=False) is True


def test_requests_session_does_not_retry_non_supported_methods_or_statuses(data_storage):
    trigger = _build_trigger(data_storage)

    adapter = trigger.requests_session.get_adapter("https://api.flare.io")
    retries = adapter.max_retries

    assert retries.is_retry("DELETE", 429, has_retry_after=False) is False
    assert retries.is_retry("POST", 500, has_retry_after=False) is False


def test_run_logs_exception_when_batch_fails(data_storage):
    trigger = _build_trigger(data_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    with patch.object(FlareEventsConnector, "next_batch", side_effect=[RuntimeError("boom"), None]):
        with patch.object(FlareEventsConnector, "running", new_callable=PropertyMock, side_effect=[True, True, False]):
            trigger.run()

    trigger.log_exception.assert_called()
