# tests/test_alert_events_threshold.py
import asyncio
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from sekoiaio.triggers.alert_events_threshold import AlertEventsThresholdTrigger, AlertEventsThresholdConfiguration
from sekoiaio.triggers.helpers.state_manager import AlertStateManager

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest_asyncio.fixture
async def trigger():
    """Create an AlertEventsThresholdTrigger with a test configuration."""
    cfg = AlertEventsThresholdConfiguration(
        enable_time_threshold=True,
        enable_volume_threshold=True,
        event_count_threshold=5,
        time_window_hours=1,
    )

    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg

    # Mock state manager to avoid file I/O
    trg.state_manager = AlertStateManager("/tmp/nonexistent_state.json")
    
    yield trg

# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matches_rule_filter(trigger):
    alert = {
        "uuid": "alert-1",
        "rule": {"name": "RuleA", "uuid": "uuid-123"},
    }

    # No filter => match all
    assert trigger._matches_rule_filter(alert)

    # Single rule filter
    trigger.configuration.rule_filter = "RuleA"
    assert trigger._matches_rule_filter(alert)
    trigger.configuration.rule_filter = "non-matching"
    assert not trigger._matches_rule_filter(alert)

    # Multiple rule names filter
    trigger.configuration.rule_filter = None
    trigger.configuration.rule_names_filter = ["RuleA", "RuleB"]
    assert trigger._matches_rule_filter(alert)
    trigger.configuration.rule_names_filter = ["RuleB"]
    assert not trigger._matches_rule_filter(alert)

@pytest.mark.asyncio
async def test_evaluate_thresholds_first_occurrence(trigger):
    alert = {"uuid": "alert-1", "events_count": 10}
    result, context = await trigger._evaluate_thresholds(alert, previous_state=None)
    assert result is True
    assert context["reason"] == "first_occurrence"
    assert context["new_events"] == 10

@pytest.mark.asyncio
async def test_evaluate_thresholds_volume_and_time(trigger):
    alert = {"uuid": "alert-1", "events_count": 10}
    previous_state = {"last_triggered_event_count": 5}

    # Patch _count_events_in_time_window to return 1
    trigger._count_events_in_time_window = AsyncMock(return_value=1)
    result, context = await trigger._evaluate_thresholds(alert, previous_state)
    assert result is True
    assert "volume_threshold" in context["reason"]
    assert "time_threshold" in context["reason"]
    assert context["new_events"] == 5

@pytest.mark.asyncio
async def test_process_alert_update_invalid_notification(trigger):
    # Should handle non-dict notification gracefully
    await trigger._process_alert_update(None)  # Should not raise

@pytest.mark.asyncio
async def test_process_alert_update_no_alert_uuid(trigger):
    # Should handle missing alert_uuid gracefully
    await trigger._process_alert_update({})  # Should not raise

@pytest.mark.asyncio
async def test_process_alert_update_triggered(trigger):
    alert = {"uuid": "alert-1", "short_id": "A-1", "events_count": 10, "rule": {"name": "RuleA", "uuid": "uuid-123"}}
    
    trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    trigger._count_events_in_time_window = AsyncMock(return_value=1)
    trigger._matches_rule_filter = AsyncMock(return_value=True)
    trigger.send_event = AsyncMock()

    await trigger._process_alert_update({"alert_uuid": "alert-1"})
    trigger.send_event.assert_awaited_once()
