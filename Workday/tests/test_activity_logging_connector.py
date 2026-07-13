import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from aioresponses import aioresponses
import re

from workday.workday_activity_logging_connector import WorkdayActivityLoggingConnector
from workday.client.errors import WorkdayAuthError
from workday.metrics import events_truncated

TOKEN_URL = "https://wd3-services1.myworkday.com/ccx/oauth2/test_tenant/token"
ACTIVITY_URL_PATTERN = re.compile(
    r"^https://wd3-services1\.myworkday\.com/ccx/api/privacy/v1/test_tenant/activityLogging(\?.*)?$"
)


@pytest.mark.asyncio
async def test_fetch_activity_logs(activity_logging_connector):
    """Test activity log fetching with pagination"""

    # Mock OAuth token endpoint
    token_response = {"access_token": "mock_access_token", "token_type": "Bearer", "expires_in": 3600}

    # Mock activity logs response (first page)
    events_page1 = [
        {
            "taskId": f"task-{i}",
            "requestTime": "2025-10-14T15:30:00.000Z",
            "systemAccount": f"T000{i}",
            "activityAction": "READ",
            "ipAddress": "192.0.2.10",
            "sessionId": "abc123",
            "taskDisplayName": "Test Task",
            "deviceType": "Desktop",
            "userAgent": "Mozilla/5.0",
            "tenantId": "test_tenant",
            "tenantHost": "wd3-services1.myworkday.com",
        }
        for i in range(1000)
    ]

    # Second page (empty - end of pagination)
    events_page2 = []

    with aioresponses() as mocked:
        # Mock token request (will be called in __aenter__)
        mocked.post(
            "https://wd3-services1.myworkday.com/ccx/oauth2/test_tenant/token",
            payload=token_response,
        )

        # Use regex to match activityLogging endpoint (query string/timestamps vary)
        activity_url_pattern = re.compile(
            r"^https://wd3-services1\.myworkday\.com/ccx/api/privacy/v1/test_tenant/activityLogging(\?.*)?$"
        )

        # Mock first page request
        mocked.get(activity_url_pattern, payload=events_page1)

        # Mock second page request (empty)
        mocked.get(activity_url_pattern, payload=events_page2)

        # Execute
        total_events = 0
        batches_received = 0
        async for batch in activity_logging_connector.next_batch():
            total_events += len(batch)
            batches_received += 1

        # Assertions
        assert total_events == 1000, f"Expected 1000 events, got {total_events}"
        assert batches_received > 0, "Expected at least one batch"
        # FIXED: next_batch() doesn't call push_data_to_intakes, that's done in run()
        # So we just verify the batches were yielded correctly


@pytest.mark.asyncio
async def test_checkpoint_management(activity_logging_connector):
    """Test checkpoint save and load"""

    # Initial checkpoint should be 24 hours ago
    initial_checkpoint = activity_logging_connector.last_event_date()
    # Make it timezone-aware if it isn't
    if initial_checkpoint.tzinfo is None:
        initial_checkpoint = initial_checkpoint.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    assert (now - initial_checkpoint).total_seconds() < 86400 + 60  # 24h + 1min buffer

    # Save new checkpoint (make timezone-aware)
    new_checkpoint = datetime(2025, 10, 14, 15, 30, 0, tzinfo=timezone.utc)
    activity_logging_connector.save_checkpoint(new_checkpoint)

    # Load checkpoint
    loaded_checkpoint = activity_logging_connector.last_event_date()
    if loaded_checkpoint.tzinfo is None:
        loaded_checkpoint = loaded_checkpoint.replace(tzinfo=timezone.utc)

    assert loaded_checkpoint == new_checkpoint


@pytest.mark.asyncio
async def test_checkpoint_saved_after_collection(activity_logging_connector):
    """The checkpoint must advance only once the whole window is collected, never mid-cycle.

    Regression test: it used to be saved up-front, so a window truncated at 10,000 events lost the
    surplus permanently. We assert it is unchanged while a batch is still pending and only advances
    after the generator is fully drained.
    """
    token_response = {"access_token": "mock_access_token", "token_type": "Bearer", "expires_in": 3600}
    events_page1 = [{"taskId": f"task-{i}", "requestTime": "2025-10-14T15:30:00.000Z"} for i in range(1000)]

    # Pin an explicit starting checkpoint so last_event_date() does not fall back to the moving
    # "24h ago" default (which would change on every call).
    initial = datetime(2025, 1, 1, tzinfo=timezone.utc)
    activity_logging_connector.save_checkpoint(initial)
    before = activity_logging_connector.last_event_date()

    with aioresponses() as mocked:
        mocked.post(TOKEN_URL, payload=token_response)
        mocked.get(ACTIVITY_URL_PATTERN, payload=events_page1)
        mocked.get(ACTIVITY_URL_PATTERN, payload=[])

        gen = activity_logging_connector.next_batch()
        await gen.__anext__()  # first batch yielded, collection not finished yet

        mid = activity_logging_connector.last_event_date()
        assert mid == before, "checkpoint must not advance while collection is still in progress"

        async for _ in gen:  # drain remaining batches -> generator runs its trailing save_checkpoint
            pass

    after = activity_logging_connector.last_event_date()
    assert after > before, "checkpoint must advance once the window is fully collected"


@pytest.mark.asyncio
async def test_truncation_warning_when_pool_saturated(activity_logging_connector):
    """When the window saturates the instancesReturned pool, a warning is logged and the metric ticks."""
    activity_logging_connector.configuration.instances_returned = 1  # pool = 10,000 records

    token_response = {"access_token": "mock_access_token", "token_type": "Bearer", "expires_in": 3600}
    # Same event repeated keeps the dedup cache tiny (fast) while still counting toward the raw total.
    full_page = [{"taskId": "task-dup", "requestTime": "2025-10-14T15:30:00.000Z"}] * 1000

    truncated_before = events_truncated._value.get()

    with aioresponses() as mocked:
        mocked.post(TOKEN_URL, payload=token_response)
        for _ in range(10):  # 10 full pages of 1000 -> 10,000 raw events == pool size
            mocked.get(ACTIVITY_URL_PATTERN, payload=full_page)
        mocked.get(ACTIVITY_URL_PATTERN, payload=[])

        async for _ in activity_logging_connector.next_batch():
            pass

    assert events_truncated._value.get() == truncated_before + 1
    warning_calls = [
        c
        for c in activity_logging_connector.log.call_args_list
        if c.kwargs.get("level") == "warning" and "truncated" in c.kwargs.get("message", "")
    ]
    assert warning_calls, "a truncation warning should have been logged"


@pytest.mark.asyncio
async def test_event_deduplication(activity_logging_connector):
    """Test event cache deduplication"""

    event1 = {"taskId": "task-123", "requestTime": "2025-10-14T15:30:00.000Z"}

    event2 = {"taskId": "task-456", "requestTime": "2025-10-14T15:31:00.000Z"}

    # First time should be new
    assert activity_logging_connector._is_new_event(event1) is True
    assert activity_logging_connector._is_new_event(event2) is True

    # Second time should be duplicate
    assert activity_logging_connector._is_new_event(event1) is False
    assert activity_logging_connector._is_new_event(event2) is False


def _iso(dt: datetime) -> str:
    """Serialize a datetime the same way the connector stores cache entries."""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def test_cleanup_event_cache_removes_expired_entries(activity_logging_connector):
    """Entries older than event_cache_ttl are dropped by _cleanup_event_cache."""
    now = datetime.now(timezone.utc)
    expired = now - activity_logging_connector.event_cache_ttl - timedelta(seconds=1)
    fresh = now - timedelta(seconds=1)

    with activity_logging_connector.event_cache_store as s:
        s["expired-key"] = _iso(expired)
        s["fresh-key"] = _iso(fresh)

    activity_logging_connector._cleanup_event_cache()

    with activity_logging_connector.event_cache_store as s:
        assert "expired-key" not in s
        assert "fresh-key" in s


def test_cleanup_event_cache_drops_malformed_timestamps(activity_logging_connector):
    """Unparsable cache timestamps are removed instead of raising."""
    fresh = datetime.now(timezone.utc) - timedelta(seconds=1)

    with activity_logging_connector.event_cache_store as s:
        s["valid-key"] = _iso(fresh)
        s["invalid-key"] = "not-a-timestamp"

    activity_logging_connector._cleanup_event_cache()

    with activity_logging_connector.event_cache_store as s:
        assert "invalid-key" not in s
        assert "valid-key" in s


# ---------------------------------------------------------------------------
# fetch_events pagination edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_events_retries_on_transient_error(activity_logging_connector):
    """A transient fetch error is retried (slept over) rather than aborting the cycle."""
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))

    client = MagicMock()
    # First call raises, retry succeeds with a short last page, then the loop ends.
    client.fetch_activity_logs = AsyncMock(
        side_effect=[
            RuntimeError("boom"),
            [{"taskId": "t1", "requestTime": "2025-10-14T15:30:00.000Z"}],
        ]
    )

    batches = []
    with patch("workday.workday_activity_logging_connector.asyncio.sleep", new=AsyncMock()):
        async for batch in activity_logging_connector.fetch_events(client):
            batches.append(batch)

    # The transient error was retried and the single event was still yielded.
    assert client.fetch_activity_logs.await_count == 2
    assert [e["taskId"] for b in batches for e in b] == ["t1"]


@pytest.mark.asyncio
async def test_fetch_events_yields_remaining_batch_on_short_page(activity_logging_connector):
    """A final page shorter than the limit flushes the pending batch and stops paginating."""
    activity_logging_connector.configuration.chunk_size = 10_000  # keep everything in one batch
    activity_logging_connector.configuration.limit = 1000
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))

    short_page = [{"taskId": f"t{i}", "requestTime": "2025-10-14T15:30:00.000Z"} for i in range(3)]
    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(return_value=short_page)

    batches = []
    async for batch in activity_logging_connector.fetch_events(client):
        batches.append(batch)

    # Only one page fetched (short page < limit ends pagination) and the batch was flushed.
    assert client.fetch_activity_logs.await_count == 1
    assert sum(len(b) for b in batches) == 3


@pytest.mark.asyncio
async def test_fetch_events_short_page_all_duplicates_yields_nothing(activity_logging_connector):
    """A short final page containing only duplicates ends the cycle without yielding an empty batch."""
    activity_logging_connector.configuration.limit = 1000
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))

    dup = {"taskId": "seen", "requestTime": "2025-10-14T15:30:00.000Z"}
    # Prime the cache so the event is already a known duplicate.
    activity_logging_connector._is_new_event(dup)

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(return_value=[dup])

    batches = [b async for b in activity_logging_connector.fetch_events(client)]

    assert client.fetch_activity_logs.await_count == 1
    assert batches == []  # nothing new -> no batch yielded on the short page


@pytest.mark.asyncio
async def test_async_run_push_failure_propagates(activity_logging_connector):
    """A failure while pushing a batch to the intake is logged and re-raised (then retried)."""
    activity_logging_connector.next_batch = MagicMock(return_value=_one_batch_generator())
    activity_logging_connector.push_data_to_intakes = AsyncMock(side_effect=RuntimeError("intake down"))

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    # The push error path logged the failure and the outer handler logged the retry.
    error_logs = [
        c
        for c in activity_logging_connector.log.call_args_list
        if c.kwargs.get("level") == "error" and "Failed to push batch" in c.kwargs.get("message", "")
    ]
    assert error_logs
    activity_logging_connector.log_exception.assert_called_once()


# ---------------------------------------------------------------------------
# _async_run loop
# ---------------------------------------------------------------------------


def _running_then_stop():
    """PropertyMock side effect: True on the first read, False afterwards (single iteration)."""
    yield True
    while True:
        yield False


async def _one_batch_generator():
    yield [{"taskId": "t1"}]


@pytest.mark.asyncio
async def test_async_run_pushes_batches_then_sleeps(activity_logging_connector):
    """One loop iteration forwards each batch to the intake, then sleeps for `frequency`."""
    activity_logging_connector.next_batch = MagicMock(return_value=_one_batch_generator())

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ) as slept:
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    activity_logging_connector.push_data_to_intakes.assert_awaited_once_with(events=[{"taskId": "t1"}])
    slept.assert_awaited()  # slept for the configured frequency between iterations


@pytest.mark.asyncio
async def test_async_run_reraises_auth_error(activity_logging_connector):
    """A WorkdayAuthError is fatal and propagates out of the loop."""
    activity_logging_connector.next_batch = MagicMock(side_effect=WorkdayAuthError("bad creds"))

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        with pytest.raises(WorkdayAuthError):
            await activity_logging_connector._async_run()


@pytest.mark.asyncio
async def test_async_run_retries_on_generic_error(activity_logging_connector):
    """A generic error is logged and retried after a backoff sleep rather than crashing the loop."""
    activity_logging_connector.next_batch = MagicMock(side_effect=RuntimeError("transient"))

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ) as slept:
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    activity_logging_connector.log_exception.assert_called_once()
    slept.assert_awaited()  # the 60s retry backoff
