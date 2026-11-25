import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prometheus_client import Counter

from office365.management_api.checkpoint import Checkpoint
from office365.management_api.configuration import Office365Configuration
from office365.management_api.connector import FORWARD_EVENTS_DURATION, Office365Connector
from office365.management_api.errors import (
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
    FailedToListO365Subscriptions,
    SessionClosedError,
)
from office365.management_api.office365_client import Office365API


@patch.object(Counter, "inc")
async def test_send_events(mock_prometheus, connector, event):
    connector.push_data_to_intakes = AsyncMock()
    await connector.send_events([event])
    connector.log.assert_called_once_with("Pushing 1 event(s) to intake", level="info")
    mock_prometheus.assert_called_once()
    connector.push_data_to_intakes.assert_called_once_with(events=[event])


TENANT_NOT_FOUND = FailedToActivateO365Subscription(
    content_type="Audit.General",
    error_code="AF10001",
    error_message="Exception: DataServiceException: Tenant 2c126aec-d94d-4887-9fb8-3474d2c5fbcf does not exist.",
)
OTHER_ERROR = FailedToActivateO365Subscription(
    content_type="Audit.General", error_code="AF20022", error_message="Oops"
)


@pytest.mark.parametrize(
    "error,expected_level,expected_in_message,not_expected_in_message",
    [
        pytest.param(
            FailedToActivateO365Subscription(),
            "critical",
            ["Failed to activate Office365 subscriptions. The connector will produce no events."],
            [],
            id="generic_error",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": TENANT_NOT_FOUND},
                active_content_types={"Audit.SharePoint", "Audit.Exchange"},
            ),
            "error",
            [
                "Audit.General",
                "Events from Audit.Exchange, Audit.SharePoint will still be collected",
                "Microsoft Purview",
            ],
            ["will produce no events"],
            id="partial_failure_tenant_not_provisioned",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(failures={"Audit.General": OTHER_ERROR}, active_content_types=set()),
            "critical",
            ["The connector will produce no events", "Please check the error details in the connector logs."],
            ["Purview"],
            id="total_failure_other_error",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": TENANT_NOT_FOUND}, active_content_types=set()
            ),
            "critical",
            ["The connector will produce no events", "unified audit logging is not enabled", "tenant 2 "],
            [],
            id="total_failure_tenant_not_provisioned",
        ),
    ],
)
async def test_activate_subscriptions_failure(
    connector, error, expected_level, expected_in_message, not_expected_in_message
):
    connector.client.activate_subscriptions.side_effect = error

    await connector.activate_subscriptions()

    connector.client.activate_subscriptions.assert_called_once()
    connector.log_exception.assert_called_once_with(
        exception=error, message="An exception occurred when trying to subscribe to Office365 events."
    )
    connector.log.assert_called_once()
    log_call = connector.log.call_args.kwargs
    assert log_call["level"] == expected_level
    for expected in expected_in_message:
        assert expected in log_call["message"]
    for not_expected in not_expected_in_message:
        assert not_expected not in log_call["message"]


async def async_generator(iterable):
    for item in iterable:
        yield item


async def test_pull_content(connector, event):
    connector.client.list_subscriptions.return_value = ["json"]
    content_skipped = {"contentUri": " foo://example.com", "contentExpiration": "2015-05-30T17:35:00.000Z"}

    content_not_skipped_1 = {
        "contentUri": " foo://example.com",
    }
    content_not_skipped_2 = {
        "contentUri": " foo://example.com",
        "contentExpiration": (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }

    connector.client.get_subscription_contents.return_value = async_generator(
        [[content_skipped, content_not_skipped_1, content_not_skipped_2]]
    )
    connector.client.get_content.return_value = [event, event]

    gen = connector.pull_content(datetime.now() - timedelta(minutes=10), datetime.now())
    result = [item async for item in gen]
    assert len(result) == 1
    assert [json.loads(event) for event in result[0]] == [event, event, event, event]


async def test_forward_next_batches(connector, symphony_storage, event):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    now = datetime.now(tz=UTC)

    async def sleeper(_):
        asyncio.sleep(0.1)

    with (
        patch.object(connector, "pull_content", return_value=async_generator([event])) as pull_content,
        patch.object(connector, "send_events") as send_events,
        patch.object(FORWARD_EVENTS_DURATION, "labels") as prometheus_labels,
        patch("office365.management_api.checkpoint.datetime") as mock_datetime,
        patch("office365.management_api.connector.datetime") as mock_datetime2,
        patch("office365.management_api.connector.asyncio.sleep") as sleep2,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_datetime2.now.return_value = now
        mock_datetime2.side_effect = lambda *args, **kw: datetime(*args, **kw)
        sleep2.side_effect = sleeper

        await connector.forward_next_batches(checkpoint)

        pull_content.assert_called_once_with(now, now)
        send_events.assert_called_once_with(event)
        prometheus_labels.assert_called_once_with(intake_key=connector.configuration.intake_key)


async def test_forward_events_forever_stops_on_stop_event(connector, symphony_storage):
    """Test that forward_events_forever stops when running is False"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    # Mock forward_next_batches to set running to False after first call
    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            connector._stop_event.set()
        await asyncio.sleep(0.01)

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    assert not connector.running


async def test_forward_events_forever_handles_exceptions(connector, symphony_storage):
    """Test that forward_events_forever handles exceptions and continues"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Test error")
        if call_count >= 2:
            connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args[1]["message"] == "Failed to forward events"


async def test_collect_events_calls_activate_and_forward(connector, symphony_storage):
    """Test that collect_events calls activate_subscriptions and forward_events_forever"""
    connector._stop_event.set()  # Stop immediately

    with (
        patch.object(connector, "activate_subscriptions", new_callable=AsyncMock) as mock_activate,
        patch.object(connector, "forward_events_forever", new_callable=AsyncMock) as mock_forward,
    ):
        await connector.collect_events()

        mock_activate.assert_called_once()
        mock_forward.assert_called_once()


async def test_shutdown_sets_stop_event(connector):
    """Test that shutdown sets the stop event"""
    assert connector.running  # Initially running

    await connector.shutdown()

    # Verify stop event was set
    assert not connector.running


async def test_client_property_is_cached(connector):
    """Test that client property uses cached_property decorator"""
    # Verify cached_property descriptor exists on class
    assert hasattr(type(connector), "client")

    # Verify property returns same instance on multiple accesses (via fixture mock)
    client1 = connector.client
    client2 = connector.client
    assert client1 is client2


async def test_activate_subscriptions_logs_info_when_stopping(connector):
    """When the connector is shutting down, a closed-session error should be logged at info level, not re-raised."""
    connector._stop_event.set()  # self.running becomes False
    connector.client.activate_subscriptions.side_effect = SessionClosedError("closed")

    await connector.activate_subscriptions()

    connector.client.activate_subscriptions.assert_called_once()
    connector.log.assert_called_once()
    log_call = connector.log.call_args
    assert log_call.kwargs.get("level") == "info"
    assert "shutdown" in log_call.kwargs.get("message", "").lower()
    connector.log_exception.assert_not_called()


@pytest.mark.parametrize(
    "second_attempt,expected_messages",
    [
        pytest.param(
            {"Audit.General"},
            ["Office365 client session was closed unexpectedly during subscription activation; rebuilding client."],
            id="retry_succeeds",
        ),
        pytest.param(
            SessionClosedError("closed again"),
            [
                "Office365 client session was closed unexpectedly during subscription activation; rebuilding client.",
                "Office365 client session was closed again after recovery; skipping subscription activation this run.",
            ],
            id="retry_fails",
        ),
    ],
)
async def test_activate_subscriptions_recovers_when_running(connector, second_attempt, expected_messages):
    """While running, a closed-session error triggers a single retry after _reset_client."""
    connector.client.activate_subscriptions.side_effect = [SessionClosedError("closed"), second_attempt]

    with patch.object(connector, "_reset_client", wraps=connector._reset_client) as reset_spy:
        await connector.activate_subscriptions()

    assert connector.client.activate_subscriptions.call_count == 2
    reset_spy.assert_called_once()
    assert [call.kwargs["message"] for call in connector.log_exception.call_args_list] == expected_messages


async def test_forward_events_forever_exits_on_session_closed_during_shutdown(connector, symphony_storage):
    """SessionClosedError during shutdown should stop the forwarding loop cleanly."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)

    async def mock_forward_next_batches(cp):
        connector._stop_event.set()
        raise SessionClosedError("closed")

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches) as forward_mock,
        patch("office365.management_api.connector.asyncio.sleep", return_value=None) as sleep_mock,
    ):
        await connector.forward_events_forever(checkpoint)

    forward_mock.assert_called_once()
    sleep_mock.assert_not_called()  # no retry-sleep after a shutdown-triggered closure
    connector.log.assert_called()
    info_calls = [call for call in connector.log.call_args_list if call.kwargs.get("level") == "info"]
    assert any("shutdown" in call.kwargs.get("message", "").lower() for call in info_calls)


async def test_forward_events_forever_resets_client_on_unexpected_session_closed(connector, symphony_storage):
    """An unexpected SessionClosedError should reset the client and let the loop continue to the next iteration."""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    call_count = 0

    async def mock_forward_next_batches(cp):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise SessionClosedError("closed")
        # Second iteration: stop the loop cleanly.
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch.object(connector, "_reset_client", wraps=connector._reset_client) as reset_spy,
        patch("office365.management_api.connector.asyncio.sleep", return_value=None),
    ):
        await connector.forward_events_forever(checkpoint)

    assert call_count == 2
    reset_spy.assert_called_once()
    connector.log_exception.assert_called_once()
    assert "rebuilding" in connector.log_exception.call_args.kwargs.get("message", "").lower()


@pytest.mark.parametrize("client_closed", [False, True])
@pytest.mark.parametrize(
    "session_state,expected_session_close_calls",
    [
        pytest.param(None, 0, id="no_session"),
        pytest.param("open", 1, id="open_session"),
        pytest.param("closed", 0, id="closed_session"),
    ],
)
async def test_shutdown(connector, client_closed, session_state, expected_session_close_calls):
    session = None if session_state is None else Mock(closed=session_state == "closed", close=AsyncMock())
    connector._client_closed = client_closed
    connector._session = session

    await connector.shutdown()

    assert not connector.running
    assert connector._client_closed is True
    assert connector.client.close.await_count == (0 if client_closed else 1)
    if session is not None:
        assert session.close.await_count == expected_session_close_calls


async def test_client_is_built_from_configuration_and_can_be_reset(
    symphony_storage, mock_azure_authentication, tenant_id
):
    connector = Office365Connector(data_path=symphony_storage)
    connector.configuration = Office365Configuration(
        intake_key="foo", client_id="client", client_secret="secret", tenant_id=tenant_id
    )

    client = connector.client
    try:
        assert isinstance(client, Office365API)
        assert client.client_id == "client"
        assert client.tenant_id == tenant_id
        assert connector.client is client
        assert connector._client_closed is False

        connector._reset_client()
        assert connector.client is not client
    finally:
        await client.close()
        await connector.client.close()


@pytest.mark.parametrize(
    "limit,nb_contents,expected_batch_sizes",
    [
        pytest.param(10_000, 0, [], id="no_content"),
        pytest.param(10_000, 3, [6], id="single_batch"),
        pytest.param(3, 3, [4, 2], id="batch_is_pushed_once_limit_is_exceeded"),
    ],
)
async def test_pull_content_batches(connector, event, limit, nb_contents, expected_batch_sizes):
    connector.limit_of_events_to_push = limit
    connector.client.list_subscriptions.return_value = ["Audit.General"]
    connector.client.get_subscription_contents.return_value = async_generator(
        [[{"contentUri": f"foo://example.com/{index}"} for index in range(nb_contents)]]
    )
    connector.client.get_content.return_value = [event, event]

    batches = [batch async for batch in connector.pull_content(datetime.now(UTC), datetime.now(UTC))]

    assert [len(batch) for batch in batches] == expected_batch_sizes


@pytest.mark.parametrize(
    "frequency,expected_sleeps",
    [
        pytest.param(60, 1, id="sleeps_until_next_pull"),
        pytest.param(0, 0, id="no_sleep_when_pull_takes_longer_than_frequency"),
    ],
)
async def test_forward_events_forever_sleep(connector, symphony_storage, frequency, expected_sleeps):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    connector._frequency = frequency

    async def mock_forward_next_batches(cp):
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=mock_forward_next_batches),
        patch("office365.management_api.connector.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        await connector.forward_events_forever(checkpoint)

    assert sleep_mock.await_count == expected_sleeps


async def test_forward_events_forever_does_not_sleep_when_stopped_while_rebuilding_client(connector, symphony_storage):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    connector.log_exception.side_effect = lambda **kwargs: connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=SessionClosedError("closed")),
        patch("office365.management_api.connector.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        await connector.forward_events_forever(checkpoint)

    connector.log_exception.assert_called_once()
    sleep_mock.assert_not_awaited()


async def test_handle_stop_signal_schedules_shutdown(connector):
    connector._handle_stop_signal(asyncio.get_running_loop())
    await asyncio.sleep(0)

    connector.log.assert_called_once_with(message="Received stop signal", level="info")
    assert not connector.running


@pytest.mark.parametrize(
    "client_created,client_closed,expected_close_calls",
    [
        pytest.param(False, False, 0, id="client_never_created"),
        pytest.param(True, False, 1, id="client_open"),
        pytest.param(True, True, 0, id="client_already_closed"),
    ],
)
async def test_collect_events_closes_client_on_exit(connector, client_created, client_closed, expected_close_calls):
    client = AsyncMock()
    if client_created:
        connector.__dict__["client"] = client
        connector._client_closed = client_closed

    with (
        patch.object(connector, "activate_subscriptions", new_callable=AsyncMock),
        patch.object(connector, "forward_events_forever", new_callable=AsyncMock),
    ):
        await connector.collect_events()

    assert client.close.await_count == expected_close_calls


async def test_activate_subscriptions_logs_active_content_types(connector):
    connector.client.activate_subscriptions.return_value = {"Audit.SharePoint", "Audit.Exchange"}

    await connector.activate_subscriptions()

    connector.log.assert_called_once_with(
        message="Office365 subscriptions are active for Audit.Exchange, Audit.SharePoint", level="info"
    )
    connector.log_exception.assert_not_called()


async def test_activate_subscriptions_logs_listing_failure(connector):
    error = FailedToListO365Subscriptions(status_code=403, body="Forbidden")
    connector.client.activate_subscriptions.side_effect = error

    await connector.activate_subscriptions()

    connector.log.assert_not_called()
    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args.kwargs["exception"] is error
    assert "ActivityFeed.Read" in connector.log_exception.call_args.kwargs["message"]
