import asyncio
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from sekoiaio.triggers.alert_events_threshold import (
    AlertEventsThresholdTrigger,
    AlertEventsThresholdConfiguration,
)
from sekoiaio.triggers.helpers.state_manager import AlertStateManager


# ----------------------------------------------------------------------
# Integration Test Fixtures
# ----------------------------------------------------------------------

@pytest_asyncio.fixture
async def fully_configured_trigger():
    """Create a fully configured trigger for integration tests."""
    cfg = AlertEventsThresholdConfiguration(
        enable_time_threshold=True,
        enable_volume_threshold=True,
        event_count_threshold=10,
        time_window_hours=2,
        check_interval_seconds=60,
        state_cleanup_days=7,
        rule_names_filter=["TestRule"],
    )

    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-api-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        state_path = Path(tmpdir) / "alert_thresholds_state.json"
        trg.state_manager = AlertStateManager(state_path)
        
        await trg._init_session()
        yield trg
        await trg._close_session()


# ----------------------------------------------------------------------
# End-to-End Workflow Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_alert_workflow_first_occurrence(fully_configured_trigger):
    """Test complete workflow for first alert occurrence."""
    alert = {
        "uuid": "alert-workflow-1",
        "short_id": "A-WF-1",
        "events_count": 15,
        "rule": {"name": "TestRule", "uuid": "rule-uuid-1"},
    }
    
    # Mock API calls
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        notification = {"alert_uuid": "alert-workflow-1"}
        await fully_configured_trigger._process_alert_update(notification)
        
        # Should trigger because it's first occurrence
        mock_send.assert_awaited_once()
        
        args = mock_send.call_args
        assert args[0][0] == "alert_threshold_met"
        
        payload = args[0][1]
        assert payload["alert"] == alert
        assert payload["trigger_context"]["reason"] == "first_occurrence"
        assert payload["trigger_context"]["new_events"] == 15


@pytest.mark.asyncio
async def test_complete_alert_workflow_volume_threshold_met(fully_configured_trigger):
    """Test complete workflow when volume threshold is met."""
    alert = {
        "uuid": "alert-workflow-2",
        "short_id": "A-WF-2",
        "events_count": 25,
        "rule": {"name": "TestRule", "uuid": "rule-uuid-2"},
    }
    
    # Set up previous state
    fully_configured_trigger.state_manager.update_alert_state(
        alert_uuid="alert-workflow-2",
        alert_short_id="A-WF-2",
        rule_uuid="rule-uuid-2",
        rule_name="TestRule",
        event_count=10,
    )
    
    # Mock API calls
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        notification = {"alert_uuid": "alert-workflow-2"}
        await fully_configured_trigger._process_alert_update(notification)
        
        # Should trigger because new_events (15) >= threshold (10)
        mock_send.assert_awaited_once()
        
        payload = mock_send.call_args[0][1]
        assert "volume_threshold" in payload["trigger_context"]["reason"]
        assert payload["trigger_context"]["new_events"] == 15


@pytest.mark.asyncio
async def test_complete_alert_workflow_no_threshold_met(fully_configured_trigger):
    """Test complete workflow when no threshold is met."""
    alert = {
        "uuid": "alert-workflow-3",
        "short_id": "A-WF-3",
        "events_count": 12,
        "rule": {"name": "TestRule", "uuid": "rule-uuid-3"},
    }
    
    # Set up previous state
    fully_configured_trigger.state_manager.update_alert_state(
        alert_uuid="alert-workflow-3",
        alert_short_id="A-WF-3",
        rule_uuid="rule-uuid-3",
        rule_name="TestRule",
        event_count=10,
    )
    
    # Mock API calls
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=0)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        notification = {"alert_uuid": "alert-workflow-3"}
        await fully_configured_trigger._process_alert_update(notification)
        
        # Should NOT trigger: new_events (2) < threshold (10) and time_window is 0
        mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_alert_workflow_filtered_by_rule(fully_configured_trigger):
    """Test complete workflow when alert is filtered by rule."""
    alert = {
        "uuid": "alert-workflow-4",
        "short_id": "A-WF-4",
        "events_count": 100,
        "rule": {"name": "OtherRule", "uuid": "rule-uuid-4"},
    }
    
    # Mock API calls
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        notification = {"alert_uuid": "alert-workflow-4"}
        await fully_configured_trigger._process_alert_update(notification)
        
        # Should NOT trigger: rule doesn't match filter
        mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_state_persistence_across_updates(fully_configured_trigger):
    """Test that state is correctly persisted across multiple updates."""
    alert_v1 = {
        "uuid": "alert-persist",
        "short_id": "A-P",
        "events_count": 10,
        "rule": {"name": "TestRule", "uuid": "rule-uuid-p"},
    }
    
    alert_v2 = {
        "uuid": "alert-persist",
        "short_id": "A-P",
        "events_count": 25,
        "rule": {"name": "TestRule", "uuid": "rule-uuid-p"},
    }
    
    # First update - first occurrence
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert_v1)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock):
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-persist"})
    
    # Check state after first update
    state_v1 = fully_configured_trigger.state_manager.get_alert_state("alert-persist")
    assert state_v1 is not None
    assert state_v1["last_triggered_event_count"] == 10
    assert state_v1["version"] == 1
    
    # Second update - more events added
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert_v2)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-persist"})
        
        # Should trigger because new_events (15) >= threshold (10)
        mock_send.assert_awaited_once()
    
    # Check state after second update
    state_v2 = fully_configured_trigger.state_manager.get_alert_state("alert-persist")
    assert state_v2["last_triggered_event_count"] == 25
    assert state_v2["version"] == 2


@pytest.mark.asyncio
async def test_multiple_alerts_processed_independently(fully_configured_trigger):
    """Test that multiple alerts are processed independently."""
    alert_1 = {
        "uuid": "alert-multi-1",
        "short_id": "A-M-1",
        "events_count": 20,
        "rule": {"name": "TestRule", "uuid": "rule-1"},
    }
    
    alert_2 = {
        "uuid": "alert-multi-2",
        "short_id": "A-M-2",
        "events_count": 30,
        "rule": {"name": "TestRule", "uuid": "rule-2"},
    }
    
    async def mock_retrieve(uuid):
        if uuid == "alert-multi-1":
            return alert_1
        return alert_2
    
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(side_effect=mock_retrieve)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        # Process first alert
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-multi-1"})
        
        # Process second alert
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-multi-2"})
        
        # Both should trigger (first occurrence)
        assert mock_send.await_count == 2
    
    # Verify independent state
    state_1 = fully_configured_trigger.state_manager.get_alert_state("alert-multi-1")
    state_2 = fully_configured_trigger.state_manager.get_alert_state("alert-multi-2")
    
    assert state_1["last_triggered_event_count"] == 20
    assert state_2["last_triggered_event_count"] == 30


@pytest.mark.asyncio
async def test_cleanup_integration(fully_configured_trigger):
    """Test state cleanup integration with processing."""
    # Add old state
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    fully_configured_trigger.state_manager._state["alerts"]["old-alert"] = {
        "alert_uuid": "old-alert",
        "last_triggered_at": old_time.isoformat(),
        "last_triggered_event_count": 10,
        "version": 1,
    }
    
    # Set cleanup to run
    fully_configured_trigger._last_cleanup = None
    
    # Process a notification
    alert = {
        "uuid": "new-alert",
        "short_id": "A-NEW",
        "events_count": 15,
        "rule": {"name": "TestRule", "uuid": "rule-new"},
    }
    
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock):
        await fully_configured_trigger._process_alert_update({"alert_uuid": "new-alert"})
    
    # Verify old state was cleaned up
    assert "old-alert" not in fully_configured_trigger.state_manager._state["alerts"]
    assert "new-alert" in fully_configured_trigger.state_manager._state["alerts"]


@pytest.mark.asyncio
async def test_error_recovery_continues_processing(fully_configured_trigger):
    """Test that errors in one alert don't stop processing others."""
    # First alert will fail
    alert_1_side_effect = RuntimeError("API Error")
    
    # Second alert will succeed
    alert_2 = {
        "uuid": "alert-recovery-2",
        "short_id": "A-R-2",
        "events_count": 15,
        "rule": {"name": "TestRule", "uuid": "rule-r-2"},
    }
    
    async def mock_retrieve(uuid):
        if uuid == "alert-recovery-1":
            raise alert_1_side_effect
        return alert_2
    
    fully_configured_trigger._retrieve_alert_from_alertapi = AsyncMock(side_effect=mock_retrieve)
    fully_configured_trigger._count_events_in_time_window = AsyncMock(return_value=5)
    
    with patch.object(fully_configured_trigger, "send_event", new_callable=AsyncMock) as mock_send:
        # Process failing alert
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-recovery-1"})
        
        # Process successful alert
        await fully_configured_trigger._process_alert_update({"alert_uuid": "alert-recovery-2"})
        
        # Only second alert should trigger
        mock_send.assert_awaited_once()
        
        payload = mock_send.call_args[0][1]
        assert payload["alert"]["uuid"] == "alert-recovery-2"


@pytest.mark.asyncio
async def test_concurrent_alert_updates():
    """Test handling concurrent updates to the same alert."""
    cfg = AlertEventsThresholdConfiguration(
        enable_volume_threshold=True,
        event_count_threshold=5,
    )
    
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        await trg._init_session()
        
        try:
            alert_v1 = {
                "uuid": "alert-concurrent",
                "short_id": "A-C",
                "events_count": 10,
                "rule": {"name": "TestRule"},
            }
            
            alert_v2 = {
                "uuid": "alert-concurrent",
                "short_id": "A-C",
                "events_count": 20,
                "rule": {"name": "TestRule"},
            }
            
            call_count = 0
            
            async def mock_retrieve(uuid):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return alert_v1
                return alert_v2
            
            trg._retrieve_alert_from_alertapi = AsyncMock(side_effect=mock_retrieve)
            trg._count_events_in_time_window = AsyncMock(return_value=0)
            
            with patch.object(trg, "send_event", new_callable=AsyncMock) as mock_send:
                # Process both updates concurrently
                await asyncio.gather(
                    trg._process_alert_update({"alert_uuid": "alert-concurrent"}),
                    trg._process_alert_update({"alert_uuid": "alert-concurrent"}),
                )
                
                # Both should trigger (first occurrence each time in this test scenario)
                assert mock_send.await_count == 2
        
        finally:
            await trg._close_session()