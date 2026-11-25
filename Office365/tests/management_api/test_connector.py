import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prometheus_client import Counter

from office365.management_api.checkpoint import Checkpoint
from office365.management_api.configuration import Office365Configuration
from office365.management_api.connector import FORWARD_EVENTS_DURATION, Office365Connector, backoff_delay
from office365.management_api.errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
    SessionClosedError,
)
from office365.management_api.office365_client import EXPECTED_SUBSCRIPTIONS, Office365API


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


LISTING_ERROR = FailedToListO365Subscriptions(status_code=403, body="Forbidden")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(FailedToActivateO365Subscription(), id="generic_error"),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(failures={"Audit.General": OTHER_ERROR}, active_content_types=set()),
            id="total_failure",
        ),
        pytest.param(LISTING_ERROR, id="listing_failure"),
    ],
)
async def test_activate_subscriptions_raises_when_no_subscription_is_active(connector, error):
    """With no active subscription, the error is raised: the SDK restarts (and eventually stops) the connector"""
    connector.client.activate_subscriptions.side_effect = error

    with pytest.raises(type(error)) as exc_info:
        await connector.activate_subscriptions()

    assert exc_info.value is error
    connector.log.assert_not_called()
    connector.log_exception.assert_not_called()


@pytest.mark.parametrize(
    "error,previous_failures,expected_in_message",
    [
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": TENANT_NOT_FOUND},
                active_content_types={"Audit.SharePoint", "Audit.Exchange"},
            ),
            0,
            [
                "Failed to activate the Office365 subscriptions for Audit.General.",
                "Events from Audit.Exchange, Audit.SharePoint are still collected",
                "Microsoft Purview",
                "Next attempt in 60 seconds",
            ],
            id="tenant_not_provisioned",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": OTHER_ERROR}, active_content_types={"Audit.Exchange"}
            ),
            10,
            ["Please check the error details", "Next attempt in 3600 seconds"],
            id="other_error_max_delay",
        ),
        pytest.param(
            LISTING_ERROR,
            1,
            [
                "Failed to list the Office365 subscriptions.",
                "Events from Audit.Exchange are still collected",
                "ActivityFeed.Read",
                "Next attempt in 120 seconds",
            ],
            id="listing_failure",
        ),
        pytest.param(
            FailedToActivateO365Subscription(),
            2,
            ["Failed to activate the Office365 subscriptions.", "Next attempt in 240 seconds"],
            id="generic_error",
        ),
    ],
)
async def test_activate_subscriptions_partial_failure(connector, error, previous_failures, expected_in_message):
    """While some subscriptions are active, the failed ones are retried with a backoff and the collection goes on"""
    connector._active_content_types = {"Audit.Exchange"}
    connector._activation_failures = previous_failures
    connector.client.activate_subscriptions.side_effect = error

    with patch("office365.management_api.connector.time.monotonic", return_value=1_000.0):
        await connector.activate_subscriptions()

    connector.log_exception.assert_called_once()
    assert connector.log_exception.call_args.kwargs["exception"] is error
    connector.log.assert_called_once()
    log_call = connector.log.call_args.kwargs
    assert log_call["level"] == "error"
    for expected in expected_in_message:
        assert expected in log_call["message"]

    assert connector._activation_pending
    assert connector._activation_failures == previous_failures + 1
    assert connector._next_activation_attempt == 1_000.0 + backoff_delay(previous_failures + 1)


@pytest.mark.parametrize(
    "error,expected_active_content_types",
    [
        pytest.param(LISTING_ERROR, {"Audit.Exchange"}, id="listing_failure_keeps_the_known_active_types"),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": OTHER_ERROR}, active_content_types={"Audit.SharePoint"}
            ),
            {"Audit.SharePoint"},
            id="activation_failure_updates_the_active_types",
        ),
    ],
)
async def test_activate_subscriptions_failure_active_content_types(connector, error, expected_active_content_types):
    connector._active_content_types = {"Audit.Exchange"}
    connector.client.activate_subscriptions.side_effect = error

    await connector.activate_subscriptions()

    assert connector._active_content_types == expected_active_content_types


async def test_activate_subscriptions_success_resets_the_retry_state(connector):
    connector._activation_failures = 3
    connector.client.activate_subscriptions.return_value = {"Audit.SharePoint", "Audit.Exchange"}

    await connector.activate_subscriptions()

    assert not connector._activation_pending
    assert connector._activation_failures == 0
    assert connector._active_content_types == {"Audit.SharePoint", "Audit.Exchange"}


@pytest.mark.parametrize(
    "pending,next_attempt,expected_calls",
    [
        pytest.param(True, 999.0, 1, id="pending_and_due"),
        pytest.param(True, 1_001.0, 0, id="pending_but_not_due"),
        pytest.param(False, 0.0, 0, id="not_pending"),
    ],
)
async def test_retry_pending_activation(connector, pending, next_attempt, expected_calls):
    connector._activation_pending = pending
    connector._next_activation_attempt = next_attempt

    with patch("office365.management_api.connector.time.monotonic", return_value=1_000.0):
        await connector._retry_pending_activation()

    assert connector.client.activate_subscriptions.await_count == expected_calls


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


async def test_pull_content_uses_the_given_content_types(connector, event):
    connector.client.get_subscription_contents.return_value = async_generator([[{"contentUri": "foo://example.com"}]])
    connector.client.get_content.return_value = [event]

    result = [item async for item in connector.pull_content(datetime.now(), datetime.now(), ["Audit.General"])]

    assert [json.loads(event) for event in result[0]] == [event]
    connector.client.list_subscriptions.assert_not_awaited()
    assert connector.client.get_subscription_contents.call_args.args == ("Audit.General",)


@pytest.mark.parametrize(
    "live_content_types,activation_pending,expected_forward,expected_warning",
    [
        pytest.param(sorted(EXPECTED_SUBSCRIPTIONS), False, True, False, id="all_subscriptions_active"),
        pytest.param(["Audit.General"], False, True, True, id="some_subscriptions_disabled"),
        pytest.param(["Audit.General"], True, True, False, id="reactivation_already_pending"),
        pytest.param([], False, False, True, id="all_subscriptions_disabled"),
    ],
)
async def test_forward_next_batches_refreshes_the_live_subscriptions(
    connector, symphony_storage, live_content_types, activation_pending, expected_forward, expected_warning
):
    """Subscriptions can be disabled while the connector is running: they are reactivated at the next cycle"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    initial_offset = checkpoint.offset
    connector._active_content_types = set(EXPECTED_SUBSCRIPTIONS)
    connector._activation_pending = activation_pending
    connector._next_activation_attempt = 1_000.0
    connector.client.list_subscriptions.return_value = live_content_types

    with patch.object(connector, "pull_content", return_value=async_generator([])) as pull_content:
        await connector.forward_next_batches(checkpoint)

    assert connector._active_content_types == set(live_content_types)
    assert connector._activation_pending == (activation_pending or expected_warning)
    assert pull_content.called == expected_forward
    if not expected_forward:
        # the checkpoint doesn't move while no subscription is active
        assert checkpoint.offset == initial_offset

    warnings = [call.kwargs for call in connector.log.call_args_list if call.kwargs.get("level") == "warning"]
    if expected_warning:
        assert connector._next_activation_attempt == 0.0
        assert len(warnings) == 1
        assert "are no longer active: they will be reactivated" in warnings[0]["message"]
    else:
        assert connector._next_activation_attempt == 1_000.0
        assert warnings == []


async def test_forward_next_batches(connector, symphony_storage, event):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    now = datetime.now(tz=UTC)
    content_types = sorted(EXPECTED_SUBSCRIPTIONS)
    connector.client.list_subscriptions.return_value = content_types

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

        pull_content.assert_called_once_with(now, now, content_types)
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


@pytest.mark.parametrize(
    "activation_pending,active_content_types,expected_activations,expected_forward_calls",
    [
        pytest.param(True, set(), 1, 1, id="retries_the_activation_then_forwards"),
        pytest.param(False, {"Audit.General"}, 0, 1, id="forwards_when_a_subscription_is_active"),
        pytest.param(False, set(), 0, 0, id="does_not_advance_the_checkpoint_without_active_subscription"),
    ],
)
async def test_forward_events_forever_retries_activation(
    connector,
    symphony_storage,
    activation_pending,
    active_content_types,
    expected_activations,
    expected_forward_calls,
):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    connector._activation_pending = activation_pending
    connector._active_content_types = active_content_types

    async def stop(*args):
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", new_callable=AsyncMock) as forward_mock,
        patch("office365.management_api.connector.asyncio.sleep", side_effect=stop),
    ):
        await connector.forward_events_forever(checkpoint)

    assert connector.client.activate_subscriptions.await_count == expected_activations
    assert forward_mock.await_count == expected_forward_calls


async def test_forward_events_forever_exits_on_error_during_shutdown(connector, symphony_storage):
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    connector._activation_pending = False
    connector._active_content_types = {"Audit.General"}

    async def fail_while_stopping(cp):
        connector._stop_event.set()
        raise FailedToListO365Subscriptions(error_message="ClientConnectionError: Connector is closed.")

    with (
        patch.object(connector, "forward_next_batches", side_effect=fail_while_stopping),
        patch("office365.management_api.connector.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        await connector.forward_events_forever(checkpoint)

    connector.log_exception.assert_not_called()
    connector.log.assert_called_once_with(
        message="Stopping event forwarding: the connector is stopping.", level="info"
    )
    sleep_mock.assert_not_awaited()


@pytest.mark.parametrize(
    "error,expected_raised",
    [
        pytest.param(FailedToGetO365SubscriptionContents(status_code=403), True, id="permission_error"),
        pytest.param(ApplicationAuthenticationFailed("Failed to get access token"), True, id="authentication_error"),
        pytest.param(FailedToGetO365SubscriptionContents(status_code=500), False, id="server_error"),
        pytest.param(ValueError("unexpected"), False, id="unexpected_error"),
    ],
)
async def test_forward_events_forever_raises_actionable_errors(connector, symphony_storage, error, expected_raised):
    """Errors that need an action from the customer are raised to the SDK; the others are retried"""
    checkpoint = Checkpoint(symphony_storage, connector.configuration.intake_key)
    connector._activation_pending = False
    connector._active_content_types = {"Audit.General"}

    async def stop(*args):
        connector._stop_event.set()

    with (
        patch.object(connector, "forward_next_batches", side_effect=error),
        patch("office365.management_api.connector.asyncio.sleep", side_effect=stop),
    ):
        if expected_raised:
            with pytest.raises(type(error)):
                await connector.forward_events_forever(checkpoint)
            connector.log_exception.assert_not_called()
        else:
            await connector.forward_events_forever(checkpoint)
            connector.log_exception.assert_called_once_with(error, message="Failed to forward events")


async def test_collect_events_resets_the_activation_state(connector):
    connector._active_content_types = {"Audit.General"}
    connector._activation_pending = False
    connector._activation_failures = 3

    with (
        patch.object(connector, "activate_subscriptions", new_callable=AsyncMock),
        patch.object(connector, "forward_events_forever", new_callable=AsyncMock),
    ):
        await connector.collect_events()

    assert connector._active_content_types == set()
    assert connector._activation_pending
    assert connector._activation_failures == 0


@pytest.mark.parametrize(
    "attempt,expected_delay",
    [
        pytest.param(0, 60, id="no_failure"),
        pytest.param(1, 60, id="first_failure"),
        pytest.param(2, 120, id="second_failure"),
        pytest.param(4, 480, id="fourth_failure"),
        pytest.param(7, 3600, id="capped"),
        pytest.param(50, 3600, id="still_capped"),
    ],
)
def test_backoff_delay(attempt, expected_delay):
    assert backoff_delay(attempt) == expected_delay


@pytest.fixture
def run_connector(connector):
    """Run the connector with a mocked `collect_events`, whose behavior is set by `asyncio.run`"""
    with (
        patch.object(connector, "collect_events", Mock()),
        patch("office365.management_api.connector.asyncio.run") as asyncio_run,
        patch.object(connector._stop_event, "wait") as stop_event_wait,
    ):
        yield connector, asyncio_run, stop_event_wait


def test_run_without_error(run_connector):
    connector, _, stop_event_wait = run_connector

    connector.run()

    assert [call.kwargs["message"] for call in connector.log.call_args_list] == [
        "Office365 Trigger has started",
        "Office365 Trigger has stopped",
    ]
    stop_event_wait.assert_not_called()


@pytest.mark.parametrize(
    "running,expected_log_exception_calls",
    [
        pytest.param(True, 1, id="while_running"),
        pytest.param(False, 0, id="during_shutdown"),
    ],
)
def test_run_handles_closed_session(run_connector, running, expected_log_exception_calls):
    connector, asyncio_run, stop_event_wait = run_connector
    asyncio_run.side_effect = SessionClosedError("closed")
    if not running:
        connector._stop_event.set()

    connector.run()

    assert connector.log_exception.call_count == expected_log_exception_calls
    stop_event_wait.assert_not_called()


@pytest.mark.parametrize(
    "error,error_count,expected_delay,expected_in_message",
    [
        pytest.param(
            ApplicationAuthenticationFailed(
                "Failed to get access token", response={"error_description": "AADSTS7000215: Invalid client secret"}
            ),
            0,
            60,
            ["ApplicationAuthenticationFailed", "client secret", "AADSTS7000215"],
            id="authentication_error",
        ),
        pytest.param(
            FailedToActivateSomeO365Subscriptions(
                failures={"Audit.General": TENANT_NOT_FOUND}, active_content_types=set()
            ),
            3,
            480,
            ["unified audit logging is not enabled"],
            id="no_active_subscription",
        ),
        pytest.param(LISTING_ERROR, 6, 3600, ["ActivityFeed.Read"], id="permission_error_max_delay"),
        pytest.param(ValueError("unexpected"), 1, 120, ["ValueError: unexpected", "Please check the error details"]),
    ],
)
def test_run_waits_then_raises_errors_to_the_sdk(
    run_connector, error, error_count, expected_delay, expected_in_message
):
    """The SDK restarts the connector on errors, counts them and stops the connector when they persist"""
    connector, asyncio_run, stop_event_wait = run_connector
    asyncio_run.side_effect = error
    connector._error_count = error_count

    with pytest.raises(type(error)):
        connector.run()

    stop_event_wait.assert_called_once_with(expected_delay)
    log_call = connector.log.call_args.kwargs
    assert log_call["level"] == "error"
    assert f"The connector will restart in {expected_delay} seconds." in log_call["message"]
    for expected in expected_in_message:
        assert expected in log_call["message"]


def test_run_does_not_raise_errors_during_shutdown(run_connector):
    connector, asyncio_run, stop_event_wait = run_connector
    asyncio_run.side_effect = LISTING_ERROR
    connector._stop_event.set()

    connector.run()

    stop_event_wait.assert_not_called()
    assert connector.log.call_args.kwargs["level"] == "info"


def test_run_does_not_raise_errors_when_stopped_while_waiting(run_connector):
    connector, asyncio_run, stop_event_wait = run_connector
    asyncio_run.side_effect = LISTING_ERROR
    stop_event_wait.side_effect = lambda delay: connector._stop_event.set()

    connector.run()

    stop_event_wait.assert_called_once_with(60)
