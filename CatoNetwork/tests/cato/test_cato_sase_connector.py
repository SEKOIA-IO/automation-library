"""Tests for Cato SASE connector."""

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import orjson
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from faker import Faker
from gql.transport.exceptions import TransportProtocolError, TransportQueryError, TransportServerError
from pydantic import ValidationError
from sekoia_automation import constants
from tenacity import Retrying, stop_after_attempt

from cato.cato_sase_connector import (
    RATE_LIMIT_DELAY,
    CatoModule,
    CatoSaseConnector,
    CatoSaseConnectorConfig,
    IncompletePushError,
    _newest_event_date,
    _query_error_message,
    _split_events,
)
from cato.metrics import EVENTS_LAG, FETCH_EVENTS_DURATION, FORWARD_EVENTS_DURATION, PUSH_EVENTS_DURATION
from client.graphql_client import CatoGraphQLClient
from client.schemas.events_feed import EventsFeedResponseSchema


@pytest.fixture
def symphony_storage():
    """Fixture for symphony temporary storage."""
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def connector(symphony_storage: str, session_faker: Faker) -> CatoSaseConnector:
    """Connector with mocked platform logs and intake push (acknowledges every event)."""
    trigger = CatoSaseConnector(module=CatoModule(), data_path=symphony_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock(side_effect=lambda events, **_kwargs: [f"id-{i}" for i in events])

    trigger.module.configuration = {"api_key": session_faker.word(), "account_id": session_faker.word()}
    trigger.configuration = CatoSaseConnectorConfig(intake_key=session_faker.uuid4())

    return trigger


def make_feed(marker: str, count: int, times: list[str] | None = None) -> EventsFeedResponseSchema:
    times = times or [datetime.now(UTC).isoformat() for _ in range(count)]
    return EventsFeedResponseSchema(
        marker=marker,
        fetchedCount=count,
        accounts=[{"records": [{"time": times[i], "fieldsMap": {"index": i}} for i in range(count)]}] if count else [],
    )


def mock_feed(connector: CatoSaseConnector, *feeds: EventsFeedResponseSchema | Exception) -> AsyncMock:
    connector._cato_client = MagicMock()
    connector._cato_client.load_events_feed = AsyncMock(side_effect=list(feeds))
    connector._cato_client.close = AsyncMock()
    return connector._cato_client.load_events_feed


def set_marker(connector: CatoSaseConnector, marker: str | None) -> None:
    with connector.context as cache:
        cache["latest_events_feed_id"] = marker


async def flush(connector: CatoSaseConnector) -> None:
    """Wait for the page pushed in the background, as the next cycle would."""
    await connector._complete_pending_push()


def forwarded_logs(connector: CatoSaseConnector) -> list[str]:
    return [c.args[0] for c in connector.log.call_args_list if c.args[0].startswith("Forwarded")]


def labelled_value(metric, name: str, intake_key: str) -> float | None:
    for sample in metric.collect()[0].samples:
        if sample.name == name and sample.labels.get("intake_key") == intake_key:
            return sample.value
    return None


# Configuration


def test_frequency_default_and_override():
    assert CatoSaseConnectorConfig(intake_key="key").frequency == 5
    assert CatoSaseConnectorConfig(intake_key="key", frequency=30).frequency == 30


@pytest.mark.parametrize("frequency", [0, -1])
def test_frequency_must_be_positive(frequency: int):
    with pytest.raises(ValidationError):
        CatoSaseConnectorConfig(intake_key="key", frequency=frequency)


# Properties


def test_latest_events_feed_id(connector: CatoSaseConnector, session_faker: Faker):
    assert connector.latest_events_feed_id is None

    marker = session_faker.uuid4()
    set_marker(connector, marker)

    assert connector.latest_events_feed_id == marker


def test_cato_client(connector: CatoSaseConnector):
    client = connector.cato_client

    assert client.api_key == connector.module.configuration.api_key
    assert client.account_id == connector.module.configuration.account_id
    assert client.base_url == "https://api.catonetworks.com/api/v1/graphql2"
    assert connector.cato_client is client


# next_batch: checkpoint ordering


@pytest.mark.asyncio
async def test_next_batch_first_run_full_push_advances_marker(connector: CatoSaseConnector):
    load = mock_feed(connector, make_feed("marker-1", 3))

    assert await connector.next_batch() == 3
    assert connector.latest_events_feed_id is None  # the page is still being pushed
    await flush(connector)

    load.assert_awaited_once_with(None)
    pushed = connector.push_events_to_intakes.call_args.kwargs["events"]
    assert [orjson.loads(event)["index"] for event in pushed] == [0, 1, 2]
    assert "event_time" in orjson.loads(pushed[0])
    assert connector.latest_events_feed_id == "marker-1"


@pytest.mark.asyncio
async def test_next_batch_resumes_from_saved_marker(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("marker-1", 1))

    await connector.next_batch()
    await flush(connector)

    load.assert_awaited_once_with("marker-0")
    assert connector.latest_events_feed_id == "marker-1"


@pytest.mark.asyncio
async def test_next_batch_keeps_marker_when_push_returns_fewer_ids(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 3))
    connector.push_events_to_intakes = MagicMock(return_value=["only-one"])

    await connector.next_batch()
    with pytest.raises(IncompletePushError):
        await flush(connector)

    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_keeps_marker_when_push_raises(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 3))
    connector.push_events_to_intakes = MagicMock(side_effect=RuntimeError("intake down"))

    await connector.next_batch()
    with pytest.raises(IncompletePushError):
        await flush(connector)

    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_empty_poll_saves_marker_without_push_nor_log(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("marker-1", 0))

    assert await connector.next_batch() == 0

    connector.push_events_to_intakes.assert_not_called()
    connector.log.assert_not_called()
    assert connector.latest_events_feed_id == "marker-1"


@pytest.mark.asyncio
async def test_next_batch_empty_marker_is_not_saved(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("", 0))

    await connector.next_batch()

    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_logs_once_when_events_forwarded(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("marker-1", 4))

    await connector.next_batch()
    connector.log.assert_not_called()
    await flush(connector)

    connector.log.assert_called_once()
    assert connector.log.call_args.args[0].startswith("Forwarded 4 events (fetch ")
    assert connector.log.call_args.kwargs["level"] == "info"


@pytest.mark.asyncio
async def test_next_batch_drops_oversized_events(connector: CatoSaseConnector):
    feed = make_feed("marker-1", 2)
    feed.accounts[0].records[1].fieldsMap["big"] = "x" * (constants.EVENT_BYTES_MAX_SIZE + 1)
    mock_feed(connector, feed)

    with patch.object(connector, "put_discarded_events") as put_discarded_events:
        await connector.next_batch()
        await flush(connector)

    put_discarded_events.assert_called_once_with(intake_key=connector.configuration.intake_key, count=1)
    assert len(connector.push_events_to_intakes.call_args.kwargs["events"]) == 1
    assert connector.latest_events_feed_id == "marker-1"
    connector.log.assert_any_call(
        f"Discarded 1 events longer than {constants.EVENT_BYTES_MAX_SIZE} characters", level="warning"
    )


# Metrics


@pytest.mark.asyncio
async def test_next_batch_metrics_on_forwarded_events(connector: CatoSaseConnector):
    intake_key = connector.configuration.intake_key
    newest = datetime.now(UTC) - timedelta(minutes=10)
    times = [(newest - timedelta(minutes=5)).isoformat(), newest.isoformat()]
    mock_feed(connector, make_feed("marker-1", 2, times))

    await connector.next_batch()
    await flush(connector)

    lag = labelled_value(EVENTS_LAG, "symphony_module_common_events_lags", intake_key)
    assert lag is not None and 600 <= lag < 660
    for metric, name in [
        (FORWARD_EVENTS_DURATION, "forward_events_duration"),
        (FETCH_EVENTS_DURATION, "fetch_events_duration"),
        (PUSH_EVENTS_DURATION, "push_events_duration"),
    ]:
        assert labelled_value(metric, f"symphony_module_common_{name}_count", intake_key) == 1


@pytest.mark.asyncio
async def test_next_batch_no_metrics_on_empty_poll(connector: CatoSaseConnector):
    intake_key = connector.configuration.intake_key
    mock_feed(connector, make_feed("marker-1", 0))

    await connector.next_batch()

    assert labelled_value(EVENTS_LAG, "symphony_module_common_events_lags", intake_key) is None
    assert (
        labelled_value(FORWARD_EVENTS_DURATION, "symphony_module_common_forward_events_duration_count", intake_key)
        is None
    )


def test_newest_event_date_handles_naive_and_invalid_times():
    feed = make_feed("m", 3, ["2024-01-01T10:00:00", "not a date", "2024-01-01T09:00:00Z"])

    assert _newest_event_date(feed) == datetime(2024, 1, 1, 10, tzinfo=UTC)
    assert _newest_event_date(make_feed("m", 0)) is None


# run_cycle: sleep and error handling


@pytest.mark.asyncio
async def test_run_cycle_refetches_immediately_while_events_are_fetched(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("marker-1", 2))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_cycle_sleeps_frequency_when_caught_up(connector: CatoSaseConnector):
    connector.configuration = CatoSaseConnectorConfig(intake_key="key", frequency=30)
    mock_feed(connector, make_feed("marker-1", 0))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    sleep.assert_awaited_once_with(30)
    connector.log.assert_not_called()


@pytest.mark.asyncio
async def test_run_cycle_incomplete_push_logs_error_and_backs_off(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("marker-1", 2), make_feed("marker-2", 2), make_feed("marker-1", 2))
    connector.push_events_to_intakes = MagicMock(return_value=[])

    # The rejection is known once the next page is fetched: that page is dropped and refetched from the saved marker
    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()
        await connector.run_cycle()
        await connector.run_cycle()

    connector.log.assert_called_once()
    assert connector.log.call_args.kwargs["level"] == "error"
    sleep.assert_awaited_once_with(2)
    assert [c.args[0] for c in load.await_args_list] == ["marker-0", "marker-1", "marker-0"]
    assert connector._pending_push is not None and connector._pending_push.marker_before == "marker-0"
    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_run_cycle_query_error_logs_vendor_message_and_sleeps(connector: CatoSaseConnector):
    mock_feed(connector, TransportQueryError("raw", errors=[{"message": "marker is invalid"}]))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    connector.log.assert_called_once_with("Cato API returned an error: marker is invalid", level="error")
    sleep.assert_awaited_once()


def levels(connector: CatoSaseConnector) -> list[str]:
    return [c.kwargs["level"] for c in connector.log.call_args_list]


async def run_cycles(connector: CatoSaseConnector, count: int) -> AsyncMock:
    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        for _ in range(count):
            await connector.run_cycle()
    return sleep


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        TransportQueryError("raw", errors=[{"message": "Permission denied"}]),
        TransportQueryError("raw", errors=[{"message": "UNAUTHORIZED: bad key"}]),
        TransportQueryError("raw", errors=[{"message": "Invalid API key"}]),
        TransportQueryError("raw", errors=[{"message": "nope", "extensions": {"code": "UNAUTHENTICATED"}}]),
        TransportQueryError("raw", errors=[{"message": "nope", "extensions": {"code": "FORBIDDEN"}}]),
        TransportServerError("unauthorized", 401),
        TransportServerError("forbidden", 403),
    ],
)
async def test_run_cycle_auth_error_is_critical_after_three_in_a_row(connector: CatoSaseConnector, error: Exception):
    mock_feed(connector, error, error, error)

    sleep = await run_cycles(connector, 3)

    assert levels(connector) == ["error", "error", "critical"]
    assert sleep.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    ["The api key field is deprecated", "missing permission on marker field", "Authentication service slow"],
)
async def test_run_cycle_non_auth_message_mentioning_auth_words_stays_error(
    connector: CatoSaseConnector, message: str
):
    error = TransportQueryError("raw", errors=[{"message": message}])
    mock_feed(connector, error, error, error, error)

    await run_cycles(connector, 4)

    assert levels(connector) == ["error"] * 4


@pytest.mark.asyncio
async def test_run_cycle_success_resets_auth_failure_counter(connector: CatoSaseConnector):
    auth = TransportServerError("unauthorized", 401)
    mock_feed(connector, auth, auth, make_feed("m", 0), auth, auth)

    await run_cycles(connector, 5)

    assert levels(connector) == ["error"] * 4


@pytest.mark.asyncio
async def test_run_cycle_successful_fetch_with_incomplete_push_resets_auth_failure_counter(
    connector: CatoSaseConnector,
):
    auth = TransportServerError("unauthorized", 401)
    mock_feed(connector, auth, make_feed("marker-1", 2), make_feed("marker-2", 2), auth, auth)
    connector.push_events_to_intakes = MagicMock(return_value=[])

    await run_cycles(connector, 5)

    assert levels(connector) == ["error"] * 4
    assert connector.latest_events_feed_id is None


@pytest.mark.asyncio
async def test_next_batch_resets_auth_failure_counter_before_push(connector: CatoSaseConnector):
    connector._consecutive_auth_failures = 2
    mock_feed(connector, make_feed("marker-1", 1))
    connector.push_events_to_intakes = MagicMock(side_effect=RuntimeError("intake down"))

    await connector.next_batch()
    with pytest.raises(IncompletePushError):
        await flush(connector)

    assert connector._consecutive_auth_failures == 0


@pytest.mark.asyncio
async def test_run_cycle_server_and_network_errors_do_not_reset_auth_failure_counter(connector: CatoSaseConnector):
    auth = TransportServerError("unauthorized", 401)
    mock_feed(connector, auth, TransportServerError("unavailable", 503), auth, TimeoutError(), auth)

    await run_cycles(connector, 5)

    assert levels(connector) == ["error"] * 4 + ["critical"]
    assert "HTTP 401" in connector.log.call_args.args[0]


@pytest.mark.asyncio
async def test_run_cycle_incomplete_push_critical_once_after_five_on_same_marker(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, *[make_feed("marker-1", 2) for _ in range(14)])
    connector.push_events_to_intakes = MagicMock(return_value=[])

    # Each rejected push takes two cycles: one starts it, the next fetches ahead then learns about the rejection
    await run_cycles(connector, 14)

    assert levels(connector) == ["error"] * 4 + ["critical"] + ["error"] * 2
    assert "marker-0" in connector.log.call_args_list[4].args[0]
    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_run_cycle_incomplete_push_counter_resets_on_success_and_marker_change(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    feeds = [make_feed("marker-1", 2) for _ in range(17)] + [make_feed("marker-2", 2) for _ in range(8)]
    mock_feed(connector, *feeds)
    # 4 rejected, 1 accepted (marker -> marker-1), 4 rejected on marker-1, then 4 rejected after a marker change.
    # A rejected push takes two cycles; the accepted one is completed by the cycle that starts the next push.
    acks = [[]] * 4 + [["a", "b"]] + [[]] * 4
    connector.push_events_to_intakes = MagicMock(side_effect=[*acks, *[[]] * 4])

    await run_cycles(connector, 17)
    assert connector.latest_events_feed_id == "marker-1"
    set_marker(connector, "marker-x")  # marker changed outside (e.g. restored context)
    await run_cycles(connector, 8)

    assert levels(connector) == ["error"] * 4 + ["info"] + ["error"] * 8


@pytest.mark.asyncio
async def test_run_cycle_http_server_error_is_error(connector: CatoSaseConnector):
    mock_feed(connector, TransportServerError("bad gateway", 502))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    connector.log.assert_called_once_with("Cato API server error: bad gateway", level="error")
    sleep.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [TimeoutError(), aiohttp.ClientConnectionError("refused"), TransportProtocolError("not json")]
)
async def test_run_cycle_network_errors_are_logged(connector: CatoSaseConnector, error: Exception):
    mock_feed(connector, error)

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    assert connector.log.call_args.kwargs["level"] == "error"
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cycle_unexpected_error_uses_log_exception(connector: CatoSaseConnector):
    error = ValueError("boom")
    mock_feed(connector, error)

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args.args[0] is error
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cycle_backoff_is_exponential_capped_and_reset(connector: CatoSaseConnector):
    connector.configuration = CatoSaseConnectorConfig(intake_key="key", frequency=5)
    mock_feed(connector, *[ValueError("boom")] * 4, make_feed("m", 1), ValueError("boom"))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        for _ in range(6):
            await connector.run_cycle()

    assert [c.args[0] for c in sleep.await_args_list] == [2, 4, 5, 5, 2]


def test_query_error_message_without_errors():
    assert _query_error_message(TransportQueryError("plain")) == "plain"
    assert _query_error_message(TransportQueryError("raw", errors=["a", {"message": "b"}])) == "a; b"


# _sleep and run loop


@pytest.mark.asyncio
async def test_sleep_steps_of_one_second_and_stops_early(connector: CatoSaseConnector):
    with patch("cato.cato_sase_connector.asyncio.sleep", new_callable=AsyncMock) as sleep:
        await connector._sleep(3)
        assert sleep.await_count == 3

        sleep.reset_mock()
        sleep.side_effect = lambda _: connector._stop_event.set()
        await connector._sleep(10)
        assert sleep.await_count == 1


def test_run_stops_when_running_is_false_and_closes_client(connector: CatoSaseConnector):
    load = mock_feed(connector, make_feed("m1", 2), make_feed("m2", 0))
    client = connector._cato_client

    async def stop_after_sleep(_: int) -> None:
        connector._stop_event.set()

    with patch.object(connector, "_sleep", side_effect=stop_after_sleep):
        connector.run()

    assert load.await_count == 2
    assert connector.latest_events_feed_id == "m2"
    client.close.assert_awaited_once()
    assert len(forwarded_logs(connector)) == 1
    assert forwarded_logs(connector)[0].startswith("Forwarded 2 events")


def test_run_does_nothing_when_already_stopped(connector: CatoSaseConnector):
    connector._stop_event.set()

    asyncio.run(connector.async_run())

    assert connector._cato_client is None


@pytest.mark.asyncio
async def test_run_cycle_401_json_body_over_real_transport_is_critical_on_third_failure(connector: CatoSaseConnector):
    async def handler(_: web.Request) -> web.Response:
        return web.json_response({"errors": [{"message": "Permission denied"}], "data": None}, status=401)

    app = web.Application()
    app.router.add_post("/graphql2", handler)

    async with TestServer(app) as server:
        connector._cato_client = CatoGraphQLClient(
            api_key="bad", account_id="account", base_url=str(server.make_url("/graphql2"))
        )
        await run_cycles(connector, 3)
        await connector._cato_client.close()

    assert levels(connector) == ["error", "error", "critical"]


# Pipeline: the next page is fetched while the previous one is pushed


@pytest.mark.asyncio
async def test_next_batch_fetches_next_page_from_pending_marker_and_saves_in_order(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("marker-1", 2), make_feed("marker-2", 2), make_feed("marker-3", 0))

    await connector.next_batch()
    assert connector.latest_events_feed_id == "marker-0"

    await connector.next_batch()
    assert connector.latest_events_feed_id == "marker-1"

    assert await connector.next_batch() == 0
    assert connector._pending_push is None
    assert connector.latest_events_feed_id == "marker-3"
    assert [c.args[0] for c in load.await_args_list] == ["marker-0", "marker-1", "marker-2"]


@pytest.mark.asyncio
async def test_next_batch_fetch_overlaps_with_push(connector: CatoSaseConnector):
    push_started = threading.Event()
    fetched_during_push = threading.Event()
    feeds = iter([make_feed("marker-1", 2), make_feed("marker-2", 0)])

    def push(events: list[str], **_kwargs) -> list[str]:
        push_started.set()
        assert fetched_during_push.wait(timeout=5), "the next page was not fetched while pushing"
        return [f"id-{i}" for i in events]

    async def load(_marker: str | None) -> EventsFeedResponseSchema:
        if connector._pending_push is not None:
            await asyncio.to_thread(push_started.wait, 5)
            fetched_during_push.set()
        return next(feeds)

    connector.push_events_to_intakes = MagicMock(side_effect=push)
    connector._cato_client = MagicMock()
    connector._cato_client.load_events_feed = load

    await connector.next_batch()
    await connector.next_batch()

    assert connector.latest_events_feed_id == "marker-2"


@pytest.mark.asyncio
async def test_run_cycle_fetch_error_keeps_pending_push_and_retries_from_its_marker(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("marker-1", 2), TimeoutError(), make_feed("marker-2", 0))

    await run_cycles(connector, 3)

    assert [c.args[0] for c in load.await_args_list] == ["marker-0", "marker-1", "marker-1"]
    assert connector.latest_events_feed_id == "marker-2"
    assert levels(connector) == ["error", "info"]


@pytest.mark.asyncio
async def test_next_batch_page_without_marker_is_pushed_but_marker_kept(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("", 2), make_feed("marker-1", 0))

    await connector.next_batch()
    await connector.next_batch()

    assert [c.args[0] for c in load.await_args_list] == ["marker-0", "marker-0"]
    assert connector.latest_events_feed_id == "marker-1"


# Push: split into batches pushed in parallel


def test_split_events_by_size_keeps_order_and_oversized_events():
    small = "a" * 10
    with patch("cato.cato_sase_connector.PUSH_BATCH_MAX_SIZE", 25):
        assert _split_events([]) == []
        assert _split_events([small, small, small]) == [[small, small], [small]]
        assert _split_events(["b" * 30, small]) == [["b" * 30], [small]]


@pytest.mark.asyncio
async def test_push_events_sends_batches_and_keeps_ids_in_order(connector: CatoSaseConnector):
    events = [f"event-{i}" for i in range(7)]

    with patch("cato.cato_sase_connector.PUSH_BATCH_MAX_SIZE", 16):
        event_ids, duration = await connector._push_events(events)

    assert connector.push_events_to_intakes.call_count == 4
    assert all(c.kwargs["sync"] is True for c in connector.push_events_to_intakes.call_args_list)
    assert event_ids == [f"id-event-{i}" for i in range(7)]
    assert duration >= 0


@pytest.mark.asyncio
async def test_push_events_counts_missing_ids_of_a_failed_batch(connector: CatoSaseConnector):
    connector.push_events_to_intakes = MagicMock(side_effect=[["id-0"], []])
    mock_feed(connector, make_feed("marker-1", 2))

    with patch("cato.cato_sase_connector.PUSH_BATCH_MAX_SIZE", 1):
        await connector.next_batch()
        with pytest.raises(IncompletePushError):
            await flush(connector)

    assert connector.latest_events_feed_id is None


# Rate limit and shutdown


@pytest.mark.asyncio
async def test_run_cycle_rate_limit_retries_after_fixed_delay_without_backoff(connector: CatoSaseConnector):
    error = TransportQueryError("raw", errors=[{"message": "rate limit for operation: eventsFeed"}])
    mock_feed(connector, error, error, error)

    sleep = await run_cycles(connector, 3)

    assert [c.args[0] for c in sleep.await_args_list] == [RATE_LIMIT_DELAY] * 3
    assert levels(connector) == ["warning"] * 3
    assert connector._consecutive_errors == 0


def test_run_completes_pending_push_on_stop(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("m1", 2))

    async def stop_after_cycle() -> None:
        await CatoSaseConnector.next_batch(connector)
        connector._stop_event.set()

    with patch.object(connector, "run_cycle", side_effect=stop_after_cycle):
        connector.run()

    assert connector.latest_events_feed_id == "m1"
    assert len(forwarded_logs(connector)) == 1
    connector._cato_client.close.assert_awaited_once()


def test_run_reports_incomplete_pending_push_on_stop(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("m1", 2))
    connector.push_events_to_intakes = MagicMock(return_value=[])

    async def stop_after_cycle() -> None:
        await CatoSaseConnector.next_batch(connector)
        connector._stop_event.set()

    with patch.object(connector, "run_cycle", side_effect=stop_after_cycle):
        connector.run()

    assert connector.latest_events_feed_id is None
    assert levels(connector) == ["error"]
    connector._cato_client.close.assert_awaited_once()


# Review follow-ups: failures around the pending push


@pytest.mark.asyncio
async def test_run_cycle_backoff_grows_while_pushes_keep_being_rejected(connector: CatoSaseConnector):
    connector.configuration = CatoSaseConnectorConfig(intake_key="key", frequency=60)
    mock_feed(connector, *[make_feed("marker-1", 2) for _ in range(6)])
    connector.push_events_to_intakes = MagicMock(return_value=[])

    sleep = await run_cycles(connector, 6)

    assert [c.args[0] for c in sleep.await_args_list] == [2, 4, 8]


@pytest.mark.asyncio
async def test_next_batch_saves_marker_of_finished_push_even_if_fetch_fails(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 2), TimeoutError())

    await connector.next_batch()
    await connector._pending_push.task
    with pytest.raises(TimeoutError):
        await connector.next_batch()

    assert connector.latest_events_feed_id == "marker-1"
    assert connector._pending_push is None


@pytest.mark.asyncio
async def test_run_cycle_push_failure_refetches_from_saved_marker(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    load = mock_feed(connector, make_feed("marker-1", 2), make_feed("marker-2", 2), make_feed("marker-1", 2))
    connector.push_events_to_intakes = MagicMock(side_effect=[RuntimeError("intake down"), ["a", "b"]])

    await run_cycles(connector, 3)

    assert [c.args[0] for c in load.await_args_list] == ["marker-0", "marker-1", "marker-0"]
    assert connector.latest_events_feed_id == "marker-0"
    assert connector._pending_push is not None and connector._pending_push.marker_before == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_empty_page_marker_not_saved_when_pending_push_fails(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 2), make_feed("marker-2", 0))
    connector.push_events_to_intakes = MagicMock(return_value=[])

    await connector.next_batch()
    with pytest.raises(IncompletePushError):
        await connector.next_batch()

    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_first_page_without_marker_keeps_no_marker(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("", 2))

    await connector.next_batch()
    await flush(connector)

    assert connector.latest_events_feed_id is None
    assert len(forwarded_logs(connector)) == 1


@pytest.mark.asyncio
async def test_run_cycle_http_429_retries_after_fixed_delay(connector: CatoSaseConnector):
    mock_feed(connector, TransportServerError("too many requests", 429))

    sleep = await run_cycles(connector, 1)

    sleep.assert_awaited_once_with(RATE_LIMIT_DELAY)
    assert levels(connector) == ["warning"]


def test_run_reports_failed_pending_push_on_stop(connector: CatoSaseConnector):
    mock_feed(connector, make_feed("m1", 2))

    async def stop_after_cycle() -> None:
        await CatoSaseConnector.next_batch(connector)
        connector._stop_event.set()

    with (
        patch.object(connector, "_push_events", side_effect=RuntimeError("boom")),
        patch.object(connector, "run_cycle", side_effect=stop_after_cycle),
    ):
        connector.run()

    assert connector.latest_events_feed_id is None
    connector.log_exception.assert_called_once()
    connector._cato_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_push_through_real_sdk_with_one_failing_batch_is_incomplete(connector: CatoSaseConnector):
    """The SDK swallows a failed request: the batch acknowledges nothing and the marker is kept."""
    received: list[list[str]] = []

    async def batch_handler(request: web.Request) -> web.Response:
        jsons = (await request.json())["jsons"]
        received.append(jsons)
        if len(received) == 2:
            return web.Response(status=500)
        return web.json_response({"event_ids": [f"id-{i}" for i in range(len(jsons))]})

    app = web.Application()
    app.router.add_post("/batch", batch_handler)

    async with TestServer(app) as server:
        connector.configuration = CatoSaseConnectorConfig(intake_key="key", intake_server=str(server.make_url("/")))
        del connector.push_events_to_intakes  # use the real SDK method
        set_marker(connector, "marker-0")
        mock_feed(connector, make_feed("marker-1", 3))

        with (
            patch("cato.cato_sase_connector.PUSH_BATCH_MAX_SIZE", 1),
            patch("cato.cato_sase_connector.MAX_CONCURRENT_PUSHES", 1),
            patch.object(
                CatoSaseConnector, "_retry", lambda _self: Retrying(stop=stop_after_attempt(1), reraise=True)
            ),
        ):
            await connector.next_batch()
            with pytest.raises(IncompletePushError, match="acknowledged 2 of 3"):
                await flush(connector)

    assert len(received) == 3
    assert connector.latest_events_feed_id == "marker-0"
