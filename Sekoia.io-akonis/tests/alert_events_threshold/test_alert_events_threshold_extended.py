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
# Fixtures
# ----------------------------------------------------------------------

@pytest_asyncio.fixture
async def trigger_with_session():
    """Create trigger with initialized session."""
    cfg = AlertEventsThresholdConfiguration(
        enable_time_threshold=True,
        enable_volume_threshold=True,
        event_count_threshold=5,
        time_window_hours=1,
    )

    trg = AlertEventsThresholdTrigger()
    trg.configuration = cfg
    trg._api_url = "https://api.test.sekoia.io"
    trg._api_key = "test-api-key"
    trg.log = MagicMock()
    trg.log_exception = MagicMock()
    
    # Mock the callback_url property to avoid FileNotFoundError
    trg.callback_url = "https://test.callback.url"
    
    # Use temp directory for state
    with tempfile.TemporaryDirectory() as tmpdir:
        trg._data_path = Path(tmpdir)
        trg.state_manager = AlertStateManager(Path(tmpdir) / "state.json")
        
        await trg._init_session()
        yield trg
        await trg._close_session()


# ----------------------------------------------------------------------
# Session Management Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_init_session_creates_session():
    """Test session initialization."""
    trigger = AlertEventsThresholdTrigger()
    trigger._api_key = "test-key"
    
    assert trigger.session is None
    await trigger._init_session()
    assert trigger.session is not None
    
    await trigger._close_session()


@pytest.mark.asyncio
async def test_close_session_handles_none():
    """Test closing session when none exists."""
    trigger = AlertEventsThresholdTrigger()
    trigger.session = None
    await trigger._close_session()  # Should not raise
    assert trigger.session is None


@pytest.mark.asyncio
async def test_close_session_closes_existing():
    """Test closing an existing session."""
    trigger = AlertEventsThresholdTrigger()
    trigger._api_key = "test-key"
    
    await trigger._init_session()
    assert trigger.session is not None
    
    await trigger._close_session()
    assert trigger.session is None


# ----------------------------------------------------------------------
# API URL Property Tests
# ----------------------------------------------------------------------

def test_alert_api_url_construction():
    """Test alert API URL construction."""
    trigger = AlertEventsThresholdTrigger()
    trigger._api_url = "https://api.sekoia.io"
    
    assert trigger.alert_api_url == "https://api.sekoia.io/v1/sic/alerts"


def test_event_api_url_construction():
    """Test event API URL construction."""
    trigger = AlertEventsThresholdTrigger()
    trigger._api_url = "https://api.sekoia.io"
    
    assert trigger.event_api_url == "https://api.sekoia.io/v2/events"


# ----------------------------------------------------------------------
# Alert Retrieval Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_alert_success(trigger_with_session):
    """Test successful alert retrieval."""
    alert_data = {
        "uuid": "alert-123",
        "short_id": "A-123",
        "events_count": 10,
    }
    
    with patch.object(
        trigger_with_session.session, "get"
    ) as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value=alert_data)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = await trigger_with_session._retrieve_alert_from_alertapi("alert-123")
        
        assert result == alert_data
        assert mock_get.called


@pytest.mark.asyncio
async def test_retrieve_alert_invalid_response(trigger_with_session):
    """Test alert retrieval with invalid response format."""
    with patch.object(
        trigger_with_session.session, "get"
    ) as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"invalid": "data"})  # Missing uuid
        mock_get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(ValueError, match="Invalid alert response format"):
            await trigger_with_session._retrieve_alert_from_alertapi("alert-123")


@pytest.mark.asyncio
async def test_retrieve_alert_with_retries(trigger_with_session):
    """Test alert retrieval retry logic."""
    from aiohttp import ClientError
    
    alert_data = {"uuid": "alert-123", "short_id": "A-123"}
    
    with patch.object(
        trigger_with_session.session, "get"
    ) as mock_get:
        # First two attempts fail, third succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.raise_for_status = MagicMock(
            side_effect=ClientError("Connection failed")
        )
        
        mock_response_success = AsyncMock()
        mock_response_success.raise_for_status = MagicMock()
        mock_response_success.json = AsyncMock(return_value=alert_data)
        
        mock_get.return_value.__aenter__.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await trigger_with_session._retrieve_alert_from_alertapi("alert-123")
        
        assert result == alert_data
        assert mock_get.call_count == 3


@pytest.mark.asyncio
async def test_retrieve_alert_max_retries_exceeded(trigger_with_session):
    """Test alert retrieval when max retries are exceeded."""
    from aiohttp import ClientError
    
    with patch.object(
        trigger_with_session.session, "get"
    ) as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=ClientError("Connection failed")
        )
        mock_get.return_value.__aenter__.return_value = mock_response
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ClientError):
                await trigger_with_session._retrieve_alert_from_alertapi("alert-123")


# ----------------------------------------------------------------------
# Event Counting Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_count_events_in_time_window_success(trigger_with_session):
    """Test successful event counting."""
    with patch.object(
        trigger_with_session.session, "post"
    ) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"total": 42})
        mock_post.return_value.__aenter__.return_value = mock_response
        
        count = await trigger_with_session._count_events_in_time_window("alert-123", 1)
        
        assert count == 42
        assert mock_post.called


@pytest.mark.asyncio
async def test_count_events_invalid_response(trigger_with_session):
    """Test event counting with invalid response."""
    with patch.object(
        trigger_with_session.session, "post"
    ) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value="invalid")  # Not a dict
        mock_post.return_value.__aenter__.return_value = mock_response
        
        count = await trigger_with_session._count_events_in_time_window("alert-123", 1)
        
        assert count == 0  # Fails open


@pytest.mark.asyncio
async def test_count_events_client_error(trigger_with_session):
    """Test event counting with client error."""
    from aiohttp import ClientError
    
    with patch.object(
        trigger_with_session.session, "post"
    ) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=ClientError("Error")
        )
        mock_post.return_value.__aenter__.return_value = mock_response
        
        count = await trigger_with_session._count_events_in_time_window("alert-123", 1)
        
        assert count == 0  # Fails open


# ----------------------------------------------------------------------
# Rule Filter Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matches_rule_filter_by_uuid(trigger_with_session):
    """Test rule filtering by UUID."""
    trigger_with_session.configuration.rule_filter = "uuid-123"
    
    alert = {
        "uuid": "alert-1",
        "rule": {"name": "RuleA", "uuid": "uuid-123"},
    }
    
    assert trigger_with_session._matches_rule_filter(alert)
    
    trigger_with_session.configuration.rule_filter = "uuid-456"
    assert not trigger_with_session._matches_rule_filter(alert)


@pytest.mark.asyncio
async def test_matches_rule_filter_multiple_names(trigger_with_session):
    """Test rule filtering with multiple names."""
    trigger_with_session.configuration.rule_filter = None
    trigger_with_session.configuration.rule_names_filter = ["RuleA", "RuleB", "RuleC"]
    
    alert_a = {"uuid": "alert-1", "rule": {"name": "RuleA"}}
    alert_b = {"uuid": "alert-2", "rule": {"name": "RuleB"}}
    alert_d = {"uuid": "alert-3", "rule": {"name": "RuleD"}}
    
    assert trigger_with_session._matches_rule_filter(alert_a)
    assert trigger_with_session._matches_rule_filter(alert_b)
    assert not trigger_with_session._matches_rule_filter(alert_d)


# ----------------------------------------------------------------------
# Threshold Evaluation Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_thresholds_no_new_events(trigger_with_session):
    """Test threshold evaluation with no new events."""
    alert = {"uuid": "alert-1", "events_count": 10}
    previous_state = {"last_triggered_event_count": 10}
    
    result, context = await trigger_with_session._evaluate_thresholds(alert, previous_state)
    
    assert result is False
    assert context == {}


@pytest.mark.asyncio
async def test_evaluate_thresholds_volume_only(trigger_with_session):
    """Test threshold evaluation with volume threshold only."""
    trigger_with_session.configuration.enable_time_threshold = False
    trigger_with_session.configuration.enable_volume_threshold = True
    trigger_with_session.configuration.event_count_threshold = 5
    
    alert = {"uuid": "alert-1", "events_count": 15}
    previous_state = {"last_triggered_event_count": 10}
    
    result, context = await trigger_with_session._evaluate_thresholds(alert, previous_state)
    
    assert result is True
    assert "volume_threshold" in context["reason"]
    assert context["new_events"] == 5


@pytest.mark.asyncio
async def test_evaluate_thresholds_time_only(trigger_with_session):
    """Test threshold evaluation with time threshold only."""
    trigger_with_session.configuration.enable_time_threshold = True
    trigger_with_session.configuration.enable_volume_threshold = False
    
    alert = {"uuid": "alert-1", "events_count": 12}
    previous_state = {"last_triggered_event_count": 10}
    
    trigger_with_session._count_events_in_time_window = AsyncMock(return_value=2)
    
    result, context = await trigger_with_session._evaluate_thresholds(alert, previous_state)
    
    assert result is True
    assert "time_threshold" in context["reason"]


@pytest.mark.asyncio
async def test_evaluate_thresholds_no_threshold_met(trigger_with_session):
    """Test threshold evaluation when no thresholds are met."""
    trigger_with_session.configuration.enable_time_threshold = True
    trigger_with_session.configuration.enable_volume_threshold = True
    trigger_with_session.configuration.event_count_threshold = 10
    
    alert = {"uuid": "alert-1", "events_count": 12}
    previous_state = {"last_triggered_event_count": 10}
    
    trigger_with_session._count_events_in_time_window = AsyncMock(return_value=0)
    
    result, context = await trigger_with_session._evaluate_thresholds(alert, previous_state)
    
    assert result is False
    assert context["reason"] == "no_threshold_met"


# ----------------------------------------------------------------------
# Process Alert Update Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_alert_update_missing_uuid(trigger_with_session):
    """Test processing notification without alert_uuid."""
    await trigger_with_session._process_alert_update({"some": "data"})
    # Should not raise, just log warning


@pytest.mark.asyncio
async def test_process_alert_update_filtered_by_rule(trigger_with_session):
    """Test alert filtered by rule filter."""
    trigger_with_session.configuration.rule_filter = "RuleB"
    
    alert = {
        "uuid": "alert-1",
        "rule": {"name": "RuleA", "uuid": "uuid-123"},
    }
    
    trigger_with_session._retrieve_alert_from_alertapi = AsyncMock(return_value=alert)
    
    await trigger_with_session._process_alert_update({"alert_uuid": "alert-1"})
    
    # Should be filtered, no send_event call


@pytest.mark.asyncio
async def test_process_alert_update_validation_error(trigger_with_session):
    """Test processing alert with validation error."""
    trigger_with_session._retrieve_alert_from_alertapi = AsyncMock(
        side_effect=ValueError("Invalid data")
    )
    
    # Should not raise, just log exception
    await trigger_with_session._process_alert_update({"alert_uuid": "alert-1"})
    
    # Verify log_exception was called
    trigger_with_session.log_exception.assert_called()


@pytest.mark.asyncio
async def test_process_alert_update_unexpected_error(trigger_with_session):
    """Test processing alert with unexpected error."""
    trigger_with_session._retrieve_alert_from_alertapi = AsyncMock(
        side_effect=RuntimeError("Unexpected")
    )
    
    # Should not raise, just log exception
    await trigger_with_session._process_alert_update({"alert_uuid": "alert-1"})
    
    # Verify log_exception was called
    trigger_with_session.log_exception.assert_called()


# ----------------------------------------------------------------------
# State Cleanup Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_old_states_first_run(trigger_with_session):
    """Test state cleanup on first run."""
    trigger_with_session._last_cleanup = None
    trigger_with_session.state_manager.cleanup_old_states = MagicMock(return_value=5)
    
    await trigger_with_session._cleanup_old_states()
    
    assert trigger_with_session._last_cleanup is not None
    assert trigger_with_session.state_manager.cleanup_old_states.called


@pytest.mark.asyncio
async def test_cleanup_old_states_skip_recent(trigger_with_session):
    """Test state cleanup skipped if recently run."""
    trigger_with_session._last_cleanup = datetime.now(timezone.utc)
    trigger_with_session.state_manager.cleanup_old_states = MagicMock(return_value=0)
    
    await trigger_with_session._cleanup_old_states()
    
    # Should skip cleanup
    assert not trigger_with_session.state_manager.cleanup_old_states.called


@pytest.mark.asyncio
async def test_cleanup_old_states_after_24h(trigger_with_session):
    """Test state cleanup runs after 24 hours."""
    trigger_with_session._last_cleanup = datetime.now(timezone.utc) - timedelta(hours=25)
    trigger_with_session.state_manager.cleanup_old_states = MagicMock(return_value=3)
    
    await trigger_with_session._cleanup_old_states()
    
    assert trigger_with_session.state_manager.cleanup_old_states.called