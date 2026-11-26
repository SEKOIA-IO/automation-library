from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_next_gen_base import (
    AuthorizationError,
    AuthorizationTimeoutError,
    FetchEventsException,
    UbikaCloudProtectorNextGenBaseConnector,
    UbikaCloudProtectorNextGenBaseConnectorConfiguration,
)


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenBaseConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = UbikaCloudProtectorNextGenBaseConnectorConfiguration(
        base_url="https://api.ubika.io/",
        namespace="sekoia",
        refresh_token="some_token_here",
        intake_key="intake_key",
        chunk_size=100,
        frequency=60,
        start_time=1,
    )
    # Make client.get a MagicMock so we can stub pagination calls
    trigger._client = MagicMock()
    yield trigger


def test_handle_response_error(trigger):
    request = httpx.Request("GET", "https://sekoia.io")
    # Handle response error with text
    response = httpx.Response(status_code=500, request=request, text="Internal Error")
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)
    assert "Internal Error" in str(m.value)
    assert "500" in str(m.value)
    # Handle response error with JSON
    response = httpx.Response(status_code=500, request=request, json={"error": "Internal Error"})
    with pytest.raises(FetchEventsException) as m:
        trigger._handle_response_error(response)
    assert "Internal Error" in str(m.value)
    # Should not raise
    response = httpx.Response(status_code=200, request=request, json={"spec": {"items": [], "nextPageToken": None}})
    trigger._handle_response_error(response)


def test_get_pages_stops_when_token_missing(trigger):
    """
    If the API returns a page with items but no nextPageToken,
    _get_pages should yield exactly that one page and then stop.
    """
    # First (and only) page: 2 dummy items, nextPageToken=None
    page = {"spec": {"items": [{"x": 1}], "nextPageToken": None}}
    trigger.client.get.return_value = httpx.Response(200, json=page)

    pages = list(trigger._get_pages(endpoint="foo", params={"filters.fromDate": 0}))
    assert pages == [[{"x": 1}]]
    # Only a single HTTP call (no second page)
    assert trigger.client.get.call_count == 1


def test_get_pages_follows_next_page_token(trigger):
    """
    _get_pages should follow nextPageToken and stop on the first empty page.
    """
    first = {"spec": {"items": [{"x": 1}], "nextPageToken": "T1"}}
    second = {"spec": {"items": [], "nextPageToken": "T2"}}
    trigger.client.get.side_effect = [
        httpx.Response(200, json=first),
        httpx.Response(200, json=second),
    ]

    pages = list(trigger._get_pages(endpoint="foo", params={"filters.fromDate": 0}))
    assert pages == [[{"x": 1}]]
    assert trigger.client.get.call_count == 2


@pytest.mark.parametrize("exc_cls", [AuthorizationError, AuthorizationTimeoutError])
def test_get_pages_raises_on_next_page_auth_errors(trigger, exc_cls):
    """
    If the second fetch (pagination) raises AuthorizationError or Timeout,
    _get_pages must bubble it up.
    """
    # First call returns a valid page with a token
    first = {"spec": {"items": [{"x": 1}], "nextPageToken": "T1"}}
    trigger.client.get.side_effect = [
        httpx.Response(200, json=first),
        exc_cls("auth failed"),
    ]

    with pytest.raises(exc_cls):
        list(trigger._get_pages(endpoint="foo", params={"filters.fromDate": 0}))

    # 2 calls: initial + follow-up
    assert trigger.client.get.call_count == 2


def test_filter_processed_events_skips_dedup_when_event_id_is_none(trigger):
    trigger.events_cache.clear()
    trigger.get_event_id = MagicMock(side_effect=[None, None])

    events = [{"bad": 1}, {"bad": 1}]
    filtered = trigger.filter_processed_events(events)

    assert filtered == events
    assert len(trigger.events_cache) == 0


def test_filter_processed_events_deduplicates_when_event_id_exists(trigger):
    trigger.events_cache.clear()
    trigger.get_event_id = MagicMock(side_effect=["evt-1", "evt-1"])

    events = [{"a": 1}, {"a": 1}]
    filtered = trigger.filter_processed_events(events)

    assert filtered == [events[0]]
    assert "evt-1" in trigger.events_cache


def test_get_event_id_not_implemented_on_base(trigger):
    with pytest.raises(NotImplementedError):
        trigger.get_event_id({"foo": "bar"})


def test_get_event_timestamp(trigger):
    assert trigger.get_event_timestamp({"timestamp": "1747326567848"}) == 1747326567848
    assert trigger.get_event_timestamp({"timestamp": 1747326567848}) == 1747326567848
    assert trigger.get_event_timestamp({}) is None
    assert trigger.get_event_timestamp({"timestamp": "not-a-number"}) is None


def test_most_recent_timestamp_seen_backfills_from_start_time(trigger):
    """No checkpoint in context -> backfill start_time hours."""
    trigger.configuration.start_time = 2
    with trigger.context as cache:
        cache.clear()

    expected = datetime.now(UTC) - timedelta(hours=2)
    result = datetime.fromtimestamp(trigger.most_recent_timestamp_seen / 1000, tz=UTC)
    assert abs((result - expected).total_seconds()) < 2


def test_most_recent_timestamp_seen_start_time_zero(trigger):
    """start_time == 0 -> now."""
    trigger.configuration.start_time = 0
    with trigger.context as cache:
        cache.clear()

    result = datetime.fromtimestamp(trigger.most_recent_timestamp_seen / 1000, tz=UTC)
    assert abs((result - datetime.now(UTC)).total_seconds()) < 2


def test_most_recent_timestamp_seen_reads_ms_checkpoint(trigger):
    ts = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = ts

    assert trigger.most_recent_timestamp_seen == ts


def test_most_recent_timestamp_seen_reads_legacy_iso_checkpoint(trigger):
    """Legacy `most_recent_date_seen` (ISO) is honored for upgrade continuity."""
    dt = datetime.now(UTC) - timedelta(hours=3)
    with trigger.context as cache:
        cache["most_recent_date_seen"] = dt.isoformat()

    result = datetime.fromtimestamp(trigger.most_recent_timestamp_seen / 1000, tz=UTC)
    assert abs((result - dt).total_seconds()) < 1


def test_most_recent_timestamp_seen_clamps_to_one_week(trigger):
    old = datetime.now(UTC) - timedelta(days=60)
    with trigger.context as cache:
        cache["most_recent_timestamp_seen"] = int(old.timestamp() * 1000)

    result = datetime.fromtimestamp(trigger.most_recent_timestamp_seen / 1000, tz=UTC)
    one_week_ago = datetime.now(UTC) - timedelta(days=7)
    assert abs((result - one_week_ago).total_seconds()) < 2


def test_load_and_save_events_cache(trigger):
    with trigger.cache_context as cache:
        cache["events_cache"] = ["h1", "h2", "h1"]

    loaded = trigger.load_events_cache()
    assert set(loaded.keys()) == {"h1", "h2"}

    trigger.events_cache = loaded
    trigger.events_cache["h3"] = True
    trigger.save_events_cache()

    with trigger.cache_context as cache:
        assert set(cache["events_cache"]) == {"h1", "h2", "h3"}
