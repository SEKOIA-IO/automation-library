"""Tests for Cato SASE connector."""

import asyncio
from datetime import UTC, datetime, timedelta
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import orjson
import pytest
from faker import Faker
from gql.transport.exceptions import TransportProtocolError, TransportQueryError, TransportServerError
from sekoia_automation import constants

from cato.cato_sase_connector import (
    CatoModule,
    CatoSaseConnector,
    CatoSaseConnectorConfig,
    _newest_event_date,
    _query_error_message,
)
from cato.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION
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
    trigger.push_events_to_intakes = MagicMock(side_effect=lambda events, sync=False: [f"id-{i}" for i in events])

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


def labelled_value(metric, name: str, intake_key: str) -> float | None:
    for sample in metric.collect()[0].samples:
        if sample.name == name and sample.labels.get("intake_key") == intake_key:
            return sample.value
    return None


# Configuration


def test_frequency_default_and_override():
    assert CatoSaseConnectorConfig(intake_key="key").frequency == 60
    assert CatoSaseConnectorConfig(intake_key="key", frequency=5).frequency == 5


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

    load.assert_awaited_once_with("marker-0")
    assert connector.latest_events_feed_id == "marker-1"


@pytest.mark.asyncio
async def test_next_batch_keeps_marker_when_push_returns_fewer_ids(connector: CatoSaseConnector):
    from cato.cato_sase_connector import IncompletePushError

    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 3))
    connector.push_events_to_intakes = MagicMock(return_value=["only-one"])

    with pytest.raises(IncompletePushError):
        await connector.next_batch()

    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_next_batch_keeps_marker_when_push_raises(connector: CatoSaseConnector):
    set_marker(connector, "marker-0")
    mock_feed(connector, make_feed("marker-1", 3))
    connector.push_events_to_intakes = MagicMock(side_effect=RuntimeError("intake down"))

    with pytest.raises(RuntimeError):
        await connector.next_batch()

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

    connector.log.assert_called_once_with("Forwarded 4 events", level="info")


@pytest.mark.asyncio
async def test_next_batch_drops_oversized_events(connector: CatoSaseConnector):
    feed = make_feed("marker-1", 2)
    feed.accounts[0].records[1].fieldsMap["big"] = "x" * (constants.EVENT_BYTES_MAX_SIZE + 1)
    mock_feed(connector, feed)

    await connector.next_batch()

    assert len(connector.push_events_to_intakes.call_args.kwargs["events"]) == 1
    assert connector.latest_events_feed_id == "marker-1"
    connector.log.assert_any_call(
        f"Discarded 1 events larger than {constants.EVENT_BYTES_MAX_SIZE} bytes", level="warning"
    )


# Metrics


@pytest.mark.asyncio
async def test_next_batch_metrics_on_forwarded_events(connector: CatoSaseConnector):
    intake_key = connector.configuration.intake_key
    newest = datetime.now(UTC) - timedelta(minutes=10)
    times = [(newest - timedelta(minutes=5)).isoformat(), newest.isoformat()]
    mock_feed(connector, make_feed("marker-1", 2, times))

    await connector.next_batch()

    lag = labelled_value(EVENTS_LAG, "symphony_module_common_events_lags", intake_key)
    assert lag is not None and 600 <= lag < 660
    assert (
        labelled_value(FORWARD_EVENTS_DURATION, "symphony_module_common_forward_events_duration_count", intake_key)
        == 1
    )


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
    mock_feed(connector, make_feed("marker-1", 2))
    connector.push_events_to_intakes = MagicMock(return_value=[])

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    connector.log.assert_called_once()
    assert connector.log.call_args.kwargs["level"] == "error"
    sleep.assert_awaited_once_with(2)
    assert connector.latest_events_feed_id == "marker-0"


@pytest.mark.asyncio
async def test_run_cycle_query_error_logs_vendor_message_and_sleeps(connector: CatoSaseConnector):
    mock_feed(connector, TransportQueryError("raw", errors=[{"message": "marker is invalid"}]))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    connector.log.assert_called_once_with("Cato API returned an error: marker is invalid", level="error")
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cycle_query_permission_error_is_critical(connector: CatoSaseConnector):
    mock_feed(connector, TransportQueryError("raw", errors=[{"message": "Permission denied"}]))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    assert connector.log.call_args.kwargs["level"] == "critical"
    sleep.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [401, 403])
async def test_run_cycle_http_auth_error_is_critical(connector: CatoSaseConnector, code: int):
    mock_feed(connector, TransportServerError("unauthorized", code))

    with patch.object(connector, "_sleep", new_callable=AsyncMock) as sleep:
        await connector.run_cycle()

    assert connector.log.call_args.kwargs["level"] == "critical"
    sleep.assert_awaited_once()


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
    connector.log.assert_called_once_with("Forwarded 2 events", level="info")


def test_run_does_nothing_when_already_stopped(connector: CatoSaseConnector):
    connector._stop_event.set()

    asyncio.run(connector.async_run())

    assert connector._cato_client is None
