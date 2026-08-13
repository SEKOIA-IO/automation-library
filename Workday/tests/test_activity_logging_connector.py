import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from aioresponses import aioresponses
import json
import re

from types import SimpleNamespace

from sekoia_automation.aio.connector import AsyncConnector

from workday.workday_activity_logging_connector import (
    EVENT_CACHE_SIZE,
    MAX_LOG_MESSAGE_CHARS,
    WorkdayActivityLoggingConfiguration,
    WorkdayActivityLoggingConnector,
)
from workday.client.errors import WorkdayAuthError
from workday.metrics import EVENTS_LAG, EVENTS_TRUNCATED


def _make_connector(data_path, **config):
    """Build a connector on a given data path, so cache persistence can be tested across restarts."""
    module = MagicMock()
    module.configuration = SimpleNamespace(
        workday_host="wd3-services1.myworkday.com",
        tenant_name="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        refresh_token="test_refresh_token",
    )
    module.load_config = MagicMock(
        return_value=WorkdayActivityLoggingConfiguration(intake_key="test_intake_key", **config)
    )

    connector = WorkdayActivityLoggingConnector(module=module, data_path=data_path)
    connector.push_data_to_intakes = AsyncMock()
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    return connector


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

    truncated = EVENTS_TRUNCATED.labels(intake_key=activity_logging_connector.configuration.intake_key)
    truncated_before = truncated._value.get()

    with aioresponses() as mocked:
        mocked.post(TOKEN_URL, payload=token_response)
        for _ in range(10):  # 10 full pages of 1000 -> 10,000 raw events == pool size
            mocked.get(ACTIVITY_URL_PATTERN, payload=full_page)
        mocked.get(ACTIVITY_URL_PATTERN, payload=[])

        async for _ in activity_logging_connector.next_batch():
            pass

    assert truncated._value.get() == truncated_before + 1
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


@pytest.mark.asyncio
async def test_filter_new_events_dedups_within_and_across_pages(activity_logging_connector):
    """The page-level filter drops duplicates inside a page and against previously cached pages."""
    e1 = {"taskId": "a", "requestTime": "2025-10-14T15:30:00.000Z"}
    e2 = {"taskId": "b", "requestTime": "2025-10-14T15:31:00.000Z"}

    # Duplicate inside the same page is collapsed to a single event.
    assert activity_logging_connector._filter_new_events([e1, e2, e1]) == [e1, e2]
    # Everything already cached from the previous page is filtered out.
    assert activity_logging_connector._filter_new_events([e1, e2]) == []


def test_filter_new_events_performs_no_disk_io(activity_logging_connector):
    """Regression: deduplicating a page must not touch the cache file at all.

    The original implementation opened a PersistentJSON context per event, and leaving that context
    rewrites the whole file — making a page cost (page size x cache size) and throttling production
    collection to ~0.38s/event. Dedup is now purely in-memory; persistence happens once per cycle.
    """
    page = [{"taskId": f"t{i}", "requestTime": "2025-10-14T15:30:00.000Z"} for i in range(500)]

    store = activity_logging_connector.event_cache_store
    with patch.object(type(store), "dump", autospec=True) as dump:
        activity_logging_connector._filter_new_events(page)

    assert dump.call_count == 0, f"dedup must not write to disk, got {dump.call_count} rewrites"


def test_events_cache_is_bounded(mock_data_path):
    """The dedup cache is an LRU bounded by EVENT_CACHE_SIZE and cannot grow without limit.

    The unbounded cache was the root cause of the throttling, so the bound is structural here
    rather than merely time-based. The bound is an internal constant, not a connector setting:
    a value chosen too large silently reintroduces the throttling it exists to prevent.
    """
    with patch("workday.workday_activity_logging_connector.EVENT_CACHE_SIZE", 10):
        connector = _make_connector(mock_data_path)

        page = [{"taskId": f"t{i}", "requestTime": "2025-10-14T15:30:00.000Z"} for i in range(100)]
        connector._filter_new_events(page)

        assert len(connector.events_cache) == 10, "cache must never exceed its maxsize"
        # The most recent keys are the ones retained (LRU eviction).
        assert connector._cache_key(page[-1]) in connector.events_cache
        assert connector._cache_key(page[0]) not in connector.events_cache

    assert EVENT_CACHE_SIZE == 100_000


def test_events_cache_survives_a_restart(mock_data_path):
    """The cache is persisted per cycle and restored on startup, so restarts do not re-forward."""
    event = {"taskId": "a", "requestTime": "2025-10-14T15:30:00.000Z"}

    first = _make_connector(mock_data_path)
    assert first._filter_new_events([event]) == [event]
    first._save_events_cache()

    # A brand new connector on the same data path must still consider the event as seen.
    second = _make_connector(mock_data_path)
    assert second._filter_new_events([event]) == []


@pytest.mark.asyncio
async def test_events_lag_reports_how_far_behind_collection_is(activity_logging_connector):
    """The standard EVENTS_LAG gauge is published so a growing backlog is visible in monitoring.

    This is the signal that was missing when the connector silently fell days behind.
    """
    # A checkpoint 5 days behind: the capped window ends ~5 days ago, so the lag is ~5 days.
    activity_logging_connector.save_checkpoint(datetime.now(timezone.utc) - timedelta(days=5))

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(return_value=[])

    async for _ in activity_logging_connector.fetch_events(client):
        pass

    lag = EVENTS_LAG.labels(intake_key=activity_logging_connector.configuration.intake_key)._value.get()
    # 5 days behind, minus the one hour of window that was just collected.
    assert timedelta(days=4).total_seconds() < lag < timedelta(days=5).total_seconds()


def test_events_cache_reads_the_legacy_mapping_format(mock_data_path):
    """A cache written by <=0.2.x ({key: timestamp}) is still honoured after the upgrade."""
    legacy = _make_connector(mock_data_path)
    with legacy.event_cache_store as s:
        s["legacy-key"] = "2025-10-14T15:30:00.000Z"

    connector = _make_connector(mock_data_path)

    assert "legacy-key" in connector.events_cache


@pytest.mark.asyncio
async def test_fetch_events_caps_window_when_checkpoint_is_far_behind(activity_logging_connector):
    """A checkpoint days behind is collected one capped window at a time, not in one huge request."""
    far_behind = datetime.now(timezone.utc) - timedelta(days=5)
    activity_logging_connector.save_checkpoint(far_behind)

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(return_value=[])

    async for _ in activity_logging_connector.fetch_events(client):
        pass

    kwargs = client.fetch_activity_logs.await_args.kwargs
    window = kwargs["to_time"] - kwargs["from_time"]
    assert window == timedelta(minutes=60), f"window should be capped to 60min, got {window}"

    # The checkpoint advanced by exactly one window, so the next cycle resumes where this one ended.
    assert activity_logging_connector.last_event_date() == far_behind + timedelta(minutes=60)
    assert activity_logging_connector._window_was_capped is True


@pytest.mark.asyncio
async def test_fetch_events_does_not_cap_a_window_already_within_bounds(activity_logging_connector):
    """A checkpoint that is up to date keeps the normal `now - 2min` window and is not flagged."""
    activity_logging_connector.save_checkpoint(datetime.now(timezone.utc) - timedelta(minutes=10))

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(return_value=[])

    async for _ in activity_logging_connector.fetch_events(client):
        pass

    window = (
        client.fetch_activity_logs.await_args.kwargs["to_time"]
        - client.fetch_activity_logs.await_args.kwargs["from_time"]
    )
    assert window < timedelta(minutes=60)
    assert activity_logging_connector._window_was_capped is False


@pytest.mark.asyncio
async def test_async_run_skips_frequency_sleep_while_catching_up(activity_logging_connector):
    """While draining a backlog the loop must not idle for `frequency`, but still yields control."""
    activity_logging_connector.next_batch = MagicMock(return_value=_one_batch_generator())
    activity_logging_connector._window_was_capped = True
    activity_logging_connector.configuration.frequency = 3600

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ) as slept:
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    # It yields to the event loop (1s) instead of sleeping the full polling frequency.
    slept.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_async_run_emits_heartbeat_each_iteration(activity_logging_connector):
    """Each cycle marks the connector alive, even when no event reaches the intake.

    `seconds_without_events` is 6h on Connector and only a successful push refreshes it, so a quiet
    or failing window would otherwise look like a hung process.
    """

    async def _empty():
        return
        yield  # pragma: no cover - generator with no yield

    activity_logging_connector.next_batch = MagicMock(return_value=_empty())
    activity_logging_connector.heartbeat = MagicMock()

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    activity_logging_connector.heartbeat.assert_called_once()
    activity_logging_connector.push_data_to_intakes.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_events_aborts_page_after_max_attempts(activity_logging_connector):
    """A durably failing page aborts the cycle instead of retrying forever."""
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))
    before = activity_logging_connector.last_event_date()

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(side_effect=RuntimeError("api down"))

    with (
        patch("workday.workday_activity_logging_connector.asyncio.sleep", new=AsyncMock()),
        patch("workday.workday_activity_logging_connector.MAX_PAGE_ATTEMPTS", 3),
    ):
        batches = [b async for b in activity_logging_connector.fetch_events(client)]

    assert client.fetch_activity_logs.await_count == 3, "should stop after MAX_PAGE_ATTEMPTS"
    assert batches == []
    # The checkpoint must NOT advance: the window is retried in full on the next cycle.
    assert activity_logging_connector.last_event_date() == before


@pytest.mark.asyncio
async def test_fetch_events_flushes_collected_batch_before_aborting(activity_logging_connector):
    """Pages already collected are yielded even when a later page fails permanently."""
    activity_logging_connector.configuration.chunk_size = 10_000  # keep page 1 pending in the batch
    activity_logging_connector.configuration.limit = 1000
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))

    full_page = [{"taskId": f"t{i}", "requestTime": "2025-10-14T15:30:00.000Z"} for i in range(1000)]
    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(side_effect=[full_page, RuntimeError("boom"), RuntimeError("boom")])

    with (
        patch("workday.workday_activity_logging_connector.asyncio.sleep", new=AsyncMock()),
        patch("workday.workday_activity_logging_connector.MAX_PAGE_ATTEMPTS", 2),
    ):
        batches = [b async for b in activity_logging_connector.fetch_events(client)]

    assert sum(len(b) for b in batches) == 1000, "the successfully collected page must not be lost"


@pytest.mark.asyncio
async def test_fetch_events_recovers_after_a_transient_failure(activity_logging_connector):
    """A page that fails once then succeeds resets the attempt counter and keeps paginating."""
    activity_logging_connector.save_checkpoint(datetime(2025, 1, 1, tzinfo=timezone.utc))

    client = MagicMock()
    client.fetch_activity_logs = AsyncMock(
        side_effect=[RuntimeError("blip"), [{"taskId": "t1", "requestTime": "2025-10-14T15:30:00.000Z"}]]
    )

    with patch("workday.workday_activity_logging_connector.asyncio.sleep", new=AsyncMock()):
        batches = [b async for b in activity_logging_connector.fetch_events(client)]

    assert [e["taskId"] for b in batches for e in b] == ["t1"]
    # Recovery means the cycle completed normally, so the checkpoint advanced.
    assert activity_logging_connector.last_event_date() > datetime(2025, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# fetch_events pagination edge cases
# ---------------------------------------------------------------------------


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


async def _two_event_batch_generator():
    yield [{"taskId": "t1"}, {"taskId": "t2"}]


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
async def test_async_run_reports_rejected_batch_as_error(activity_logging_connector):
    """A batch the intake rejects is logged as an error, not as a success.

    The SDK's async chunk sender logs HTTP errors instead of raising, so a rejected push returns
    an empty id list. Counting the submitted batch size here used to report success for events
    that were never ingested (e.g. an intake key not yet propagated, HTTP 422).
    """
    activity_logging_connector.next_batch = MagicMock(return_value=_one_batch_generator())
    activity_logging_connector.push_data_to_intakes = AsyncMock(return_value=[])

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    logged = [call.kwargs for call in activity_logging_connector.log.call_args_list]
    rejections = [c for c in logged if c.get("level") == "error" and "rejected by the intake" in c.get("message", "")]
    assert len(rejections) == 1, "a fully rejected batch must be logged once as an error"
    assert "0/1 events accepted" in rejections[0]["message"]

    successes = [c for c in logged if "successfully forwarded" in c.get("message", "")]
    assert not successes, "no success must be logged when the intake accepted nothing"


@pytest.mark.asyncio
async def test_async_run_counts_accepted_events_not_submitted_ones(activity_logging_connector):
    """A partially accepted batch is reported with the count returned by the intake."""
    activity_logging_connector.next_batch = MagicMock(return_value=_two_event_batch_generator())
    activity_logging_connector.push_data_to_intakes = AsyncMock(return_value=["evt-1"])

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    logged = [call.kwargs for call in activity_logging_connector.log.call_args_list]
    rejections = [c for c in logged if c.get("level") == "error" and "rejected by the intake" in c.get("message", "")]
    assert len(rejections) == 1
    assert "1/2 events accepted" in rejections[0]["message"]


@pytest.mark.asyncio
async def test_async_run_emits_one_customer_facing_summary_per_cycle(activity_logging_connector):
    """Pagination and batching internals go to the pod logs; the customer gets a single summary.

    The GUI only receives `self.log` calls, and the SDK drops any line whose exact text repeats
    within 60s. Keeping the mechanics out of `self.log` is what stops the actionable lines from
    being crowded out.
    """
    activity_logging_connector.next_batch = MagicMock(return_value=_one_batch_generator())
    activity_logging_connector._last_lag = 30.0

    with patch.object(type(activity_logging_connector), "running", new_callable=PropertyMock) as running, patch(
        "workday.workday_activity_logging_connector.sleep", new=AsyncMock()
    ):
        running.side_effect = _running_then_stop()
        await activity_logging_connector._async_run()

    messages = [c.kwargs.get("message", "") for c in activity_logging_connector.log.call_args_list]

    summaries = [m for m in messages if "Collected" in m or "No new events" in m]
    assert len(summaries) == 1, f"expected exactly one cycle summary, got {summaries}"
    assert "up to date" in summaries[0]

    # Mechanics must not reach the customer-facing logger.
    for noise in ("Batch ready for intake", "Moving to next page", "context entered", "Fetching page"):
        assert not any(noise in m for m in messages), f"{noise!r} should stay in the pod logs"


@pytest.mark.asyncio
async def test_lag_summary_flags_a_backlog(activity_logging_connector):
    """The summary distinguishes 'up to date' from a backlog being caught up."""
    activity_logging_connector._last_lag = 30.0
    activity_logging_connector._window_was_capped = False
    assert activity_logging_connector._lag_summary() == "up to date"

    activity_logging_connector._last_lag = 7200.0
    activity_logging_connector._window_was_capped = True
    assert activity_logging_connector._lag_summary() == "catching up, 120 min behind real time"

    activity_logging_connector._window_was_capped = False
    assert activity_logging_connector._lag_summary() == "120 min behind real time"


def _rejection_payload(count: int) -> str:
    """Rebuild the batch API's answer to a fully rejected chunk: one error object per event."""
    return json.dumps(
        {
            "event_ids": [],
            "errors": True,
            "summary": {"total": count, "success": 0, "error": count},
            "results": [{"status": 422, "error": {"message": "Invalid intake key", "code": "INVALID_INTAKE_KEY"}}]
            * count,
        }
    )


def test_log_truncates_oversized_intake_errors(activity_logging_connector):
    """A rejected 1,000-event chunk must not reach the platform as a ~90,000 character line.

    The SDK builds that message inside `_async_send_chunk` (not overridable) and hands it to
    `log_exception`, which funnels into `log` -- the only seam where it can be capped.
    """
    message = f"Chunk 0 error (422) on attempt 1: {_rejection_payload(1000)}"
    assert len(message) > 50_000  # the raw line really is that big

    sent = []
    with patch.object(AsyncConnector, "log", side_effect=lambda msg, *a, **k: sent.append(msg)):
        # `log` is mocked on the fixture, so call the real implementation explicitly.
        WorkdayActivityLoggingConnector.log(activity_logging_connector, message, "error")

    assert len(sent) == 1
    assert len(sent[0]) < MAX_LOG_MESSAGE_CHARS + 100
    assert sent[0].startswith("Chunk 0 error (422) on attempt 1")  # cause still identifiable
    assert "INVALID_INTAKE_KEY" in sent[0]
    assert f"truncated, {len(message)} chars total" in sent[0]


def test_log_leaves_normal_messages_untouched(activity_logging_connector):
    """Ordinary log lines pass through unchanged."""
    message = "Batch 3 successfully forwarded to intake (1000 events)"

    sent = []
    with patch.object(AsyncConnector, "log", side_effect=lambda msg, *a, **k: sent.append(msg)):
        WorkdayActivityLoggingConnector.log(activity_logging_connector, message, "info")

    assert sent == [message]


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
