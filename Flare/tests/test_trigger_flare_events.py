import json
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests

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


def _response(status_code, body=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Client Error")
    return response


def _fake_client(pages):
    """Build a Flare client whose feed returns `pages`, a list of `(events, next_cursor)`.

    An event set to `None` has its details answered with a 404.
    """
    details = {}
    scroll_pages = []
    for page_index, (events, next_cursor) in enumerate(pages):
        items = []
        for event_index, event in enumerate(events):
            uid = f"uid-{page_index}-{event_index}"
            items.append({"metadata": {"uid": uid}})
            details[uid] = _response(404) if event is None else _response(200, event)
        scroll_pages.append(_response(200, {"items": items, "next": next_cursor}))

    client = MagicMock()
    client.scroll.return_value = scroll_pages
    client.get.side_effect = lambda url, params: details[params["uid"]]
    return client


def _run_next_batch(trigger, fake_client, fake_limiter=None):
    fake_limiter = fake_limiter or MagicMock()
    with patch.object(FlareEventsConnector, "client", new_callable=PropertyMock, return_value=fake_client):
        with patch.object(FlareEventsConnector, "limiter", new_callable=PropertyMock, return_value=fake_limiter):
            trigger.next_batch()


def _event(uid, event_type="chat_message"):
    return {"activity": {"header": {"uid": uid, "type": event_type}}}


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_first_run_builds_initial_filter(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    fake_client = _fake_client([([_event("evt-1")], "cursor-1"), ([_event("evt-2", "forum_post")], "cursor-2")])
    fake_limiter = MagicMock()

    _run_next_batch(trigger, fake_client, fake_limiter)

    assert trigger.cursor.offset == "cursor-2"
    assert trigger.push_events_to_intakes.called

    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed_events) == 2
    assert json.loads(pushed_events[0])["header"]["uid"] == "evt-1"

    call_kwargs = fake_client.scroll.call_args.kwargs
    payload = call_kwargs["json"]
    assert payload["size"] == 10
    assert payload["order"] == "asc"
    assert "query" not in payload
    assert payload["from"] == ""
    assert "filters" in payload
    assert call_kwargs["method"] == "POST"
    assert call_kwargs["url"] == "/firework/v4/events/tenant/_search"
    fake_client.get.assert_any_call(url="/firework/v2/activities/", params={"uid": "uid-0-0"})
    # Pages and events are throttled by the connector's single limiter.
    assert fake_limiter.tick.called


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_resumes_from_checkpoint(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "previous-cursor"
    fake_client = _fake_client([([_event("evt-3", "listing")], "next-cursor")])

    _run_next_batch(trigger, fake_client)

    payload = fake_client.scroll.call_args.kwargs["json"]
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
    fake_client = _fake_client([])

    _run_next_batch(trigger, fake_client)

    payload = fake_client.scroll.call_args.kwargs["json"]
    assert payload["size"] == 10


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_streams_events_in_batches_of_100(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)

    # 25 pages of 10 events each; every event of a page shares the same `next` cursor.
    pages = [([_event(f"evt-{page}-{index}") for index in range(10)], f"cursor-{page}") for page in range(1, 26)]
    _run_next_batch(trigger, _fake_client(pages))

    # 250 events are streamed as batches of 100, 100 then a final 50.
    push_sizes = [len(call.kwargs["events"]) for call in trigger.push_events_to_intakes.call_args_list]
    assert push_sizes == [100, 100, 50]

    # The checkpoint only advances on page boundaries, never mid-page.
    assert trigger.cursor.offset == "cursor-25"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_no_event_keeps_cursor(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "stable-cursor"

    _run_next_batch(trigger, _fake_client([]))

    assert trigger.cursor.offset == "stable-cursor"
    trigger.push_events_to_intakes.assert_not_called()


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_skips_events_whose_details_are_not_found(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    fake_client = _fake_client([([_event("evt-1"), None, _event("evt-3")], "cursor-1")])

    _run_next_batch(trigger, fake_client)

    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert [json.loads(event)["header"]["uid"] for event in pushed_events] == ["evt-1", "evt-3"]
    assert trigger.cursor.offset == "cursor-1"
    # A single summary line, no per-event log nor exception.
    trigger.log.assert_called_once_with(
        "Forwarded 2 events to the intake (1 unavailable events skipped)", level="info"
    )
    trigger.log_exception.assert_not_called()


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_moves_past_pages_of_unavailable_events(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "previous-cursor"

    _run_next_batch(trigger, _fake_client([([None, None], "cursor-1")]))

    trigger.push_events_to_intakes.assert_not_called()
    assert trigger.cursor.offset == "cursor-1"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_raises_on_other_detail_errors(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    fake_client = _fake_client([([_event("evt-1")], "cursor-1")])
    fake_client.get.side_effect = lambda url, params: _response(500)

    with pytest.raises(requests.HTTPError):
        _run_next_batch(trigger, fake_client)

    trigger.push_events_to_intakes.assert_not_called()


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_pushes_complete_pages_before_failing(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.cursor.offset = "previous-cursor"
    fake_client = _fake_client(
        [([_event("evt-1"), _event("evt-2")], "cursor-1"), ([_event("evt-3"), _event("evt-4")], "cursor-2")]
    )
    responses = fake_client.get.side_effect
    fake_client.get.side_effect = lambda url, params: (
        _response(429) if params["uid"] == "uid-1-1" else responses(url, params)
    )

    with pytest.raises(requests.HTTPError):
        _run_next_batch(trigger, fake_client)

    # Only the fully read first page is forwarded; the second one will be read again.
    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert [json.loads(event)["header"]["uid"] for event in pushed_events] == ["evt-1", "evt-2"]
    assert trigger.cursor.offset == "cursor-1"


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_drops_chat_message_context(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    event = _event("evt-1")
    event["activity"]["data"] = {"message": "hello", "olders": [{"message": "a"}], "newers": [{"message": "b"}]}

    _run_next_batch(trigger, _fake_client([([event], "cursor-1")]))

    pushed_event = json.loads(trigger.push_events_to_intakes.call_args.kwargs["events"][0])
    assert pushed_event["data"] == {"message": "hello"}


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_run_logs_exception_when_batch_fails(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    with patch.object(FlareEventsConnector, "next_batch", side_effect=[RuntimeError("boom"), None]):
        with patch.object(FlareEventsConnector, "running", new_callable=PropertyMock, side_effect=[True, True, False]):
            trigger.run()

    trigger.log_exception.assert_called()
    # Back off for one period after a failure.
    mock_sleep.assert_called_once_with(60)
