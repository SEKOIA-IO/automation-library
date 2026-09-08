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

    call_kwargs = fake_client.scroll_events.call_args.kwargs
    payload = call_kwargs["json"]
    assert payload["size"] == 10
    assert payload["order"] == "asc"
    assert "query" not in payload
    assert payload["from"] == ""
    assert "filters" in payload
    assert call_kwargs["pages_url"] == "/firework/v4/events/tenant/_search"
    # Both limiters use the connector's single throttle setting to avoid the SDK's 1s/page default.
    assert call_kwargs["_pages_limiter"] is fake_limiter
    assert call_kwargs["_events_limiter"] is fake_limiter


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_resumes_from_checkpoint(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "previous-cursor"

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = [
        SimpleNamespace(
            event={"activity": {"header": {"uid": "evt-3", "type": "listing"}}},
            next="next-cursor",
        )
    ]

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    payload = fake_client.scroll_events.call_args.kwargs["json"]
    assert "query" not in payload
    assert payload["from"] == "previous-cursor"
    assert "filters" not in payload
    assert trigger.cursor.offset == "next-cursor"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_caps_page_size_to_api_limit(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.configuration = {
        "intake_key": "intake_key",
        "frequency": 60,
        "page_size": 100,
        "initial_hours_lookback": 1,
        "throttle_seconds": 0,
    }

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = []

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    payload = fake_client.scroll_events.call_args.kwargs["json"]
    assert payload["size"] == 10


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_streams_events_in_batches_of_100(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)

    # 25 pages of 10 events each; every event of a page shares the same `next` cursor.
    results = []
    for page in range(1, 26):
        cursor = f"cursor-{page}"
        for index in range(10):
            results.append(
                SimpleNamespace(
                    event={"activity": {"header": {"uid": f"evt-{page}-{index}", "type": "chat_message"}}},
                    next=cursor,
                )
            )

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = results
    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    # 250 events are streamed as batches of 100, 100 then a final 50.
    push_sizes = [len(call.kwargs["events"]) for call in trigger.push_events_to_intakes.call_args_list]
    assert push_sizes == [100, 100, 50]

    # The checkpoint only advances on page boundaries, never mid-page.
    assert trigger.cursor.offset == "cursor-25"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_no_event_keeps_cursor(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "stable-cursor"

    fake_client = MagicMock()
    fake_client.scroll_events.return_value = []

    fake_limiter = MagicMock()

    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()

    assert trigger.cursor.offset == "stable-cursor"
    trigger.push_events_to_intakes.assert_not_called()


def test_run_logs_exception_when_batch_fails(data_storage):
    trigger = _build_trigger(data_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    with patch.object(FlareEventsConnector, "next_batch", side_effect=[RuntimeError("boom"), None]):
        with patch.object(FlareEventsConnector, "running", new_callable=PropertyMock, side_effect=[True, True, False]):
            trigger.run()

    trigger.log_exception.assert_called()
