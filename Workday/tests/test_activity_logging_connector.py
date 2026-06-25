import pytest
from datetime import datetime, timedelta, timezone
from aioresponses import aioresponses
import re

from workday.workday_activity_logging_connector import WorkdayActivityLoggingConnector
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
