import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, PropertyMock, patch

import orjson
import pytest
import requests
from prometheus_client import REGISTRY
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE

from flareio_modules import FlareIOModule
from flareio_modules.http import REQUEST_TIMEOUT, TimeoutHTTPAdapter
from flareio_modules.trigger_flare_events import FlareEventsConnector, ThreadSafeLimiter

# `time.sleep` is patched in the connector's module by most tests; keep the real ones for the timing tests
real_sleep = time.sleep
real_monotonic = time.monotonic


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
            items.append({"metadata": {"uid": uid, "matched_at": f"2026-11-16T14:38:{event_index:02d}Z"}})
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
def test_next_batch_adds_match_date(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    old_item = {"activity": {"header": {"uid": "evt-1"}, "metadata": {"estimated_created_at": "2021-11-25T18:26:18Z"}}}
    no_metadata = {"activity": {"header": {"uid": "evt-3"}, "metadata": None}}
    fake_client = _fake_client([([old_item, _event("evt-2"), no_metadata], "cursor-1")])

    _run_next_batch(trigger, fake_client)

    pushed = [json.loads(event) for event in trigger.push_events_to_intakes.call_args.kwargs["events"]]
    assert pushed[0]["metadata"] == {
        "estimated_created_at": "2021-11-25T18:26:18Z",
        "matched_at": "2026-11-16T14:38:00Z",
    }
    assert pushed[1]["metadata"] == {"matched_at": "2026-11-16T14:38:01Z"}
    assert pushed[2]["metadata"] == {"matched_at": "2026-11-16T14:38:02Z"}


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


def _push_one(data_storage, data: dict, event_type: str = "blog_post") -> str:
    trigger = _build_trigger(data_storage)
    event = _event("evt-1", event_type=event_type)
    event["activity"]["data"] = data
    _run_next_batch(trigger, _fake_client([([event], "cursor-1")]))
    return trigger.push_events_to_intakes.call_args.kwargs["events"][0]


@pytest.mark.parametrize("content", ["x" * 300_000, "\n" * 200_000, "é" * 300_000])
@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_cuts_oversized_content(mock_sleep, data_storage, content):
    serialized = _push_one(data_storage, {"title": "post", "content": content})

    assert len(serialized.encode("utf-8")) <= EVENT_BYTES_MAX_SIZE
    pushed = json.loads(serialized)
    assert pushed["data"]["title"] == "post"
    assert pushed["data"]["truncated_fields"] == ["content"]
    kept = pushed["data"]["content"]
    assert content.startswith(kept)
    # As much content as fits: one more character would not
    pushed["data"]["content"] = content[: len(kept) + 1]
    assert len(orjson.dumps(pushed)) > EVENT_BYTES_MAX_SIZE


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_cuts_least_useful_fields_first(mock_sleep, data_storage):
    # Like a Telegram attachment: a big extracted text, and the same long IP list twice
    ips = [f"10.0.{i // 256}.{i % 256}" for i in range(20_000)]
    data = {
        "extracted_content": "x" * 200_000,
        "features": {"ip_addresses": ips, "ip_addresses_cidr": list(ips), "emails": ["a@b.c"], "domains": ["d.e"]},
        "content": "kept",
    }

    serialized = _push_one(data_storage, data, event_type="attachment")

    assert len(serialized.encode("utf-8")) <= EVENT_BYTES_MAX_SIZE
    pushed_data = json.loads(serialized)["data"]
    assert pushed_data["truncated_fields"] == [
        "extracted_content",
        "features.ip_addresses",
        "features.ip_addresses_cidr",
    ]
    assert pushed_data["extracted_content"] == ""
    # Lists keep their first item, which is the one the parser reads
    assert pushed_data["features"]["ip_addresses"] == ips[:1]
    kept_cidrs = pushed_data["features"]["ip_addresses_cidr"]
    assert kept_cidrs == ips[: len(kept_cidrs)]
    assert len(kept_cidrs) > 1
    assert pushed_data["features"]["emails"] == ["a@b.c"]
    assert pushed_data["features"]["domains"] == ["d.e"]
    assert pushed_data["content"] == "kept"


@pytest.mark.parametrize("count", [3, 20_000])
@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_cuts_oversized_file_list(mock_sleep, data_storage, count):
    files = [f"Browsers/Edge/{i:06d}/" + "f" * (300_000 // count) for i in range(count)]
    credentials = [{"url": "https://example.com", "username": "user"}]

    serialized = _push_one(data_storage, {"files": files, "credentials": credentials}, event_type="stealer_log")

    assert len(serialized.encode("utf-8")) <= EVENT_BYTES_MAX_SIZE
    pushed_data = json.loads(serialized)["data"]
    assert pushed_data["truncated_fields"] == ["files"]
    kept = len(pushed_data["files"])
    assert files[:kept] == pushed_data["files"]
    # As close to the limit as whole items allow
    assert len(serialized.encode("utf-8")) + len(orjson.dumps(files[kept])) + 1 > EVENT_BYTES_MAX_SIZE
    assert pushed_data["credentials"] == credentials


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_cuts_parsed_lists_last(mock_sleep, data_storage):
    # Like a stealer log with thousands of credentials, or a leak listing thousands of emails
    credentials = [{"url": f"https://site-{i}.example", "username": "user", "password": "p****"} for i in range(2_000)]
    emails = [f"user{i}@example.com" for i in range(15_000)]
    data = {"files": ["a.txt"], "credentials": credentials, "features": {"emails": emails, "usernames": ["u"]}}

    serialized = _push_one(data_storage, data, event_type="stealer_log")

    assert len(serialized.encode("utf-8")) <= EVENT_BYTES_MAX_SIZE
    pushed_data = json.loads(serialized)["data"]
    assert pushed_data["truncated_fields"] == ["files", "credentials", "features.emails"]
    assert pushed_data["files"] == []
    assert pushed_data["credentials"] == []
    kept_emails = pushed_data["features"]["emails"]
    assert kept_emails == emails[: len(kept_emails)]
    assert kept_emails
    assert pushed_data["features"]["usernames"] == ["u"]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # Fits: unchanged
        ({"content": "x" * 1_000}, {"content": "x" * 1_000}),
        # Not a string or a list: left for the SDK to discard
        ({"content": {"x": "x" * 300_000}}, {"content": {"x": "x" * 300_000}}),
        # Too big because of a field that is not cut: the SDK still discards the event
        (
            {"content": "x" * 1_000, "extracted_content": "", "main": "y" * 300_000},
            {"content": "", "extracted_content": "", "main": "y" * 300_000, "truncated_fields": ["content"]},
        ),
        ({"features": {"emails": "a" * 300_000}}, {"features": {"emails": "a" * 300_000}}),
        ({"features": ["a" * 300_000]}, {"features": ["a" * 300_000]}),
    ],
)
@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_cuts_fields_only_when_needed(mock_sleep, data_storage, data, expected):
    serialized = _push_one(data_storage, data, event_type="ransomleak")

    assert json.loads(serialized)["data"] == expected


def _counter(name):
    return REGISTRY.get_sample_value(f"symphony_module_flare_{name}_total", {"intake_key": "intake_key"}) or 0


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_reports_cut_and_discarded_events(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    small = _event("evt-small")
    cut = _event("evt-cut", "paste")
    cut["activity"]["data"] = {"content": "x" * 300_000}
    # `main` is not cut: the event stays above the limit
    still_oversized = _event("evt-big", "ransomleak")
    still_oversized["activity"]["data"] = {"main": "y" * 300_000}
    truncated_before, discarded_before = _counter("truncated_events"), _counter("discarded_events")

    _run_next_batch(trigger, _fake_client([([small, cut, still_oversized], "cursor-1")]))

    assert _counter("truncated_events") - truncated_before == 1
    assert _counter("discarded_events") - discarded_before == 1
    trigger.log.assert_any_call(
        "Cut the fields content of the paste event evt-cut to fit the intake size limit", level="info"
    )
    pushed = trigger.push_events_to_intakes.call_args.kwargs["events"]
    assert len(pushed) == 3
    size = len(pushed[2].encode("utf-8"))
    trigger.log.assert_any_call(
        f"The ransomleak event evt-big is still above the intake size limit ({size} bytes) and will be discarded",
        level="warning",
    )


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_fetches_details_concurrently_in_feed_order(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.configuration.concurrency = 4
    events = [_event(f"evt-{index}") for index in range(10)]
    fake_client = _fake_client([(events, "cursor-1")])
    answer = fake_client.get.side_effect
    in_flight, max_in_flight, lock = 0, 0, threading.Lock()

    def slow_get(url, params):
        nonlocal in_flight, max_in_flight
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        # The first events answer last
        real_sleep(0.05 * (10 - int(params["uid"].rsplit("-", 1)[1])) / 10)
        with lock:
            in_flight -= 1
        return answer(url, params)

    fake_client.get.side_effect = slow_get

    _run_next_batch(trigger, fake_client)

    pushed_events = trigger.push_events_to_intakes.call_args.kwargs["events"]
    pushed = [json.loads(event)["header"]["uid"] for event in pushed_events]
    assert pushed == [f"evt-{index}" for index in range(10)]
    assert 1 < max_in_flight <= 4


@patch("flareio_modules.trigger_flare_events.time.sleep")
def test_next_batch_fails_without_waiting_for_running_calls(mock_sleep, data_storage):
    trigger = _build_trigger(data_storage)
    trigger.configuration.concurrency = 2
    fake_client = _fake_client([([_event("evt-1"), _event("evt-2")], "cursor-1")])
    answer = fake_client.get.side_effect
    hanging, release = threading.Event(), threading.Event()

    def get(url, params):
        if params["uid"] == "uid-0-0":
            hanging.wait(timeout=5)
            return _response(429)
        hanging.set()
        release.wait(timeout=10)  # a call that hangs
        return answer(url, params)

    fake_client.get.side_effect = get

    started = real_monotonic()
    try:
        with pytest.raises(requests.HTTPError):
            _run_next_batch(trigger, fake_client)
        assert real_monotonic() - started < 5
    finally:
        release.set()


def test_limiter_is_shared_by_threads(data_storage):
    trigger = _build_trigger(data_storage)
    trigger.configuration.throttle_seconds = 0.01

    limiter = trigger.limiter
    start = real_monotonic()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: limiter.tick(), range(8)))

    assert isinstance(limiter, ThreadSafeLimiter)
    # The first tick is immediate, then one every 10 ms whatever the number of threads
    assert real_monotonic() - start >= 0.07


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


def test_client_retries_flare_server_errors(data_storage):
    trigger = _build_trigger(data_storage)

    retry = trigger.client._session.get_adapter("https://api.flare.io").max_retries

    # Flare answers intermittent 500s, which the SDK's session does not retry
    assert all(retry.is_retry(method, status) for method in ("GET", "POST") for status in (429, 500, 502, 503, 504))
    assert not retry.is_retry("GET", 404)
    assert retry.total == 5


@pytest.mark.parametrize(("timeout", "expected"), [(None, REQUEST_TIMEOUT), (5, 5)])
def test_client_calls_have_a_timeout(data_storage, monkeypatch, timeout, expected):
    trigger = _build_trigger(data_storage)
    sent = {}

    def fake_send(self, request, stream, timeout, verify, cert, proxies):
        sent["timeout"] = timeout
        return requests.Response()

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    adapter = trigger.client._session.get_adapter("https://api.flare.io")
    assert isinstance(adapter, TimeoutHTTPAdapter)

    # The SDK sends its requests without a timeout
    adapter.send(requests.Request("GET", "https://api.flare.io/").prepare(), timeout=timeout)

    assert sent["timeout"] == expected
