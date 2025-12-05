import asyncio
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import os

from sekoiaio.triggers.alert_events_threshold import (
    AlertEventsThresholdTrigger,
    AlertEventsThresholdConfiguration,
    SYMPHONY_DIR,
)
from sekoiaio.triggers.helpers.state_manager import AlertStateManager


# ----------------------------------------------------------------------
# Edge Case Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alert_with_zero_events():
    """Test handling alert with zero events."""
    cfg = AlertEventsThresholdConfiguration()
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-zero", "events_count": 0}
        previous_state = None
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should trigger on first occurrence even with 0 events
        assert result is True
        assert context["new_events"] == 0


@pytest.mark.asyncio
async def test_alert_with_negative_event_delta():
    """Test handling alert where events_count decreased."""
    cfg = AlertEventsThresholdConfiguration()
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-neg", "events_count": 5}
        previous_state = {"last_triggered_event_count": 10}
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should not trigger when events decreased
        assert result is False
        assert context == {}


@pytest.mark.asyncio
async def test_alert_missing_events_count():
    """Test handling alert without events_count field."""
    cfg = AlertEventsThresholdConfiguration()
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-missing"}  # No events_count
        previous_state = None
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should handle gracefully, treating as 0
        assert result is True
        assert context["new_events"] == 0


@pytest.mark.asyncio
async def test_alert_missing_rule_info():
    """Test handling alert without rule information."""
    cfg = AlertEventsThresholdConfiguration(rule_filter="TestRule")
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    alert_no_rule = {"uuid": "alert-1"}
    alert_empty_rule = {"uuid": "alert-2", "rule": {}}
    
    # Both should not match when filter is set
    assert not trg._matches_rule_filter(alert_no_rule)
    assert not trg._matches_rule_filter(alert_empty_rule)


@pytest.mark.asyncio
async def test_notification_with_extra_fields():
    """Test processing notification with extra/unexpected fields."""
    cfg = AlertEventsThresholdConfiguration()
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        await trg._init_session()
        
        try:
            alert = {
                "uuid": "alert-extra",
                "short_id": "A-E",
                "events_count": 10,
                "rule": {"name": "TestRule"},
            }
            
            trg._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
            trg._count_events_in_time_window = AsyncMock(return_value=5)
            
            with patch.object(trg, "send_event", new_callable=AsyncMock) as mock_send:
                # Notification with extra fields
                notification = {
                    "alert_uuid": "alert-extra",
                    "extra_field": "should_be_ignored",
                    "another_field": 123,
                }
                
                await trg._process_alert_update(notification)
                
                # Should process normally
                mock_send.assert_awaited_once()
        
        finally:
            await trg._close_session()


@pytest.mark.asyncio
async def test_event_count_exactly_at_threshold():
    """Test when new events exactly match threshold."""
    cfg = AlertEventsThresholdConfiguration(
        enable_volume_threshold=True,
        enable_time_threshold=False,
        event_count_threshold=10,
    )
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-exact", "events_count": 20}
        previous_state = {"last_triggered_event_count": 10}
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should trigger: 10 new events >= 10 threshold
        assert result is True
        assert context["new_events"] == 10


@pytest.mark.asyncio
async def test_event_count_one_below_threshold():
    """Test when new events are one below threshold."""
    cfg = AlertEventsThresholdConfiguration(
        enable_volume_threshold=True,
        enable_time_threshold=False,
        event_count_threshold=10,
    )
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-below", "events_count": 19}
        previous_state = {"last_triggered_event_count": 10}
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should not trigger: 9 new events < 10 threshold
        assert result is False


@pytest.mark.asyncio
async def test_very_large_event_counts():
    """Test handling very large event counts."""
    cfg = AlertEventsThresholdConfiguration(
        enable_volume_threshold=True,
        event_count_threshold=1000000,
    )
    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        alert = {"uuid": "alert-large", "events_count": 2000000}
        previous_state = {"last_triggered_event_count": 500000}
        
        result, context = await trg._evaluate_thresholds(alert, previous_state)
        
        # Should trigger: 1,500,000 new events >= 1,000,000 threshold
        assert result is True
        assert context["new_events"] == 1500000


# ----------------------------------------------------------------------
# Initialization Tests
# ----------------------------------------------------------------------

def test_trigger_initialization_defaults():
    """Test trigger initialization with default values."""
    trg = AlertEventsThresholdTrigger()
    
    assert trg.state_manager is None
    assert trg.session is None
    assert trg._last_cleanup is None


def test_trigger_data_path_default():
    """Test default data path initialization."""
    trg = AlertEventsThresholdTrigger()
    
    # Should use SYMPHONY_DIR by default
    assert trg._data_path == SYMPHONY_DIR / "data"


def test_trigger_data_path_from_env():
    """Test data path initialization from environment."""
    with patch.dict(os.environ, {"SEKOIAIO_MODULE_DIR": "/custom/path"}):
        trg = AlertEventsThresholdTrigger()
        
        assert trg._data_path == Path("/custom/path") / "data"


def test_trigger_api_credentials_from_module():
    """Test API credentials loaded from module configuration."""
    trg = AlertEventsThresholdTrigger()
    
    # Mock module with configuration
    mock_module = MagicMock()
    mock_module.configuration.base_url = "https://api.module.sekoia.io"
    mock_module.configuration.api_key = "module-api-key"
    trg.module = mock_module
    
    # Re-initialize to load from module
    trg.__init__()
    
    assert trg._api_url == "https://api.module.sekoia.io"
    assert trg._api_key == "module-api-key"


def test_trigger_api_credentials_fallback_to_env():
    """Test API credentials fallback to environment variables."""
    with patch.dict(os.environ, {
        "SEKOIAIO_API_URL": "https://api.env.sekoia.io",
        "SEKOIAIO_API_KEY": "env-api-key"
    }):
        trg = AlertEventsThresholdTrigger()
        
        # Mock module without configuration
        trg.module = MagicMock()
        trg.module.configuration = None
        
        trg.__init__()
        
        assert trg._api_url == "https://api.env.sekoia.io"
        assert trg._api_key == "env-api-key"


# ----------------------------------------------------------------------
# Run Method Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_handles_cancellation():
    """Test run method handles asyncio.CancelledError."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    
    async def mock_next_batch():
        raise asyncio.CancelledError()
    
    trg.next_batch = mock_next_batch
    trg._close_session = AsyncMock()
    
    # Should exit cleanly without raising
    await trg.run()
    
    trg._close_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_handles_exception_with_retry():
    """Test run method handles exceptions and retries."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    
    call_count = 0
    
    async def mock_next_batch():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Transient error")
        else:
            raise asyncio.CancelledError()  # Stop the loop
    
    trg.next_batch = mock_next_batch
    trg._close_session = AsyncMock()
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await trg.run()
        
        # Should have slept once before retrying
        mock_sleep.assert_awaited_once()
        assert call_count == 2


@pytest.mark.asyncio
async def test_run_ensures_session_closed():
    """Test run method ensures session is closed on exit."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    
    async def mock_next_batch():
        raise RuntimeError("Error")
    
    trg.next_batch = mock_next_batch
    trg._close_session = AsyncMock()
    
    # Run for limited time then cancel
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Make sleep raise CancelledError to exit the loop
        mock_sleep.side_effect = asyncio.CancelledError()
        
        await trg.run()
    
    # Session should be closed even after error
    trg._close_session.assert_awaited()


# ----------------------------------------------------------------------
# Next Batch Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_next_batch_initializes_state_manager():
    """Test next_batch initializes state manager."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        
        # Mock subscribe to immediately stop
        async def mock_subscribe(*args):
            return
            yield  # Make it a generator
        
        trg._subscribe_to_notifications = mock_subscribe
        trg._close_session = AsyncMock()
        
        await trg.next_batch()
        
        # State manager should be initialized
        assert trg.state_manager is not None
        assert trg.session is not None


@pytest.mark.asyncio
async def test_next_batch_processes_notifications():
    """Test next_batch processes incoming notifications."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        
        notifications = [
            {"alert_uuid": "alert-1"},
            {"alert_uuid": "alert-2"},
        ]
        
        async def mock_subscribe(*args):
            for notification in notifications:
                yield notification
        
        trg._subscribe_to_notifications = mock_subscribe
        trg._process_alert_update = AsyncMock()
        trg._cleanup_old_states = AsyncMock()
        trg._close_session = AsyncMock()
        
        await trg.next_batch()
        
        # Should have processed both notifications
        assert trg._process_alert_update.await_count == 2


@pytest.mark.asyncio
async def test_next_batch_handles_notification_errors():
    """Test next_batch continues processing after notification errors."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        
        notifications = [
            {"alert_uuid": "alert-1"},
            {"alert_uuid": "alert-2"},
        ]
        
        async def mock_subscribe(*args):
            for notification in notifications:
                yield notification
        
        call_count = 0
        
        async def mock_process(notification):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Processing error")
            # Second one succeeds
        
        trg._subscribe_to_notifications = mock_subscribe
        trg._process_alert_update = mock_process
        trg._cleanup_old_states = AsyncMock()
        trg._close_session = AsyncMock()
        
        await trg.next_batch()
        
        # Should have attempted to process both despite first error
        assert call_count == 2


@pytest.mark.asyncio
async def test_next_batch_cancellation_stops_processing():
    """Test next_batch stops cleanly on cancellation."""
    trg = AlertEventsThresholdTrigger()
    trg.configuration = AlertEventsThresholdConfiguration()
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-key"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        
        async def mock_subscribe(*args):
            yield {"alert_uuid": "alert-1"}
            raise asyncio.CancelledError()
        
        trg._subscribe_to_notifications = mock_subscribe
        trg._process_alert_update = AsyncMock()
        trg._close_session = AsyncMock()
        
        with pytest.raises(asyncio.CancelledError):
            await trg.next_batch()
        
        # Session should still be closed
        trg._close_session.assert_awaited_once()