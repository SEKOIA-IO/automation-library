import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioresponses import aioresponses

from sekoiaio.triggers.alert_events_threshold import (
    AlertEventsThresholdConfiguration,
    AlertEventsThresholdTrigger,
)
from sekoiaio.triggers.helpers.state_manager import AlertStateManager


@pytest.fixture
def config():
    """
    Create test configuration.

    Note: In production, API credentials are automatically injected by the
    Sekoia.io backend via module context. For tests, we mock the module
    with these credentials separately (see mock_module fixture).
    """
    return AlertEventsThresholdConfiguration(
        event_count_threshold=100,
        time_window_hours=1,
        enable_volume_threshold=True,
        enable_time_threshold=True,
        check_interval_seconds=60,
    )


@pytest.fixture
def mock_module():
    """
    Create mock module with backend-provided credentials.

    Note: In production, these credentials are automatically injected by Sekoia.io
    backend and are used only for reading alert data (not for intake re-injection).
    """
    module = MagicMock()
    module.configuration.base_url = "https://app.sekoia.io"
    module.configuration.api_key = "test-api-key"
    return module


@pytest.fixture
def sample_alert():
    """Create sample alert data."""
    return {
        "uuid": "alert-uuid-1234",
        "short_id": "ALT-12345",
        "events_count": 150,
        "status": {
            "name": "Ongoing",
            "uuid": "status-uuid",
        },
        "rule": {
            "uuid": "rule-uuid-abcd",
            "name": "Suspicious PowerShell Activity",
        },
        "urgency": {
            "severity": 70,
        },
        "created_at": "2025-11-14T08:00:00.000000Z",
        "updated_at": "2025-11-14T10:30:00.000000Z",
    }


@pytest.fixture
def state_manager(tmp_path):
    """Create temporary state manager."""
    state_file = tmp_path / "test_state.json"
    return AlertStateManager(state_file)


@pytest.mark.asyncio
async def test_first_occurrence_triggers_immediately(config, mock_module, sample_alert, tmp_path):
    """Test that first time seeing an alert triggers immediately."""
    trigger = AlertEventsThresholdTrigger()
    trigger.configuration = config
    trigger.module = mock_module  # Inject mock module with credentials
    trigger._data_path = tmp_path
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = AsyncMock()

    # Set internal credentials from mock module
    trigger._api_url = mock_module.configuration.base_url
    trigger._api_key = mock_module.configuration.api_key

    state_file = tmp_path / "state.json"
    trigger.state_manager = AlertStateManager(state_file)

    with aioresponses() as mocked:
        # Mock Alert API response
        alert_url = f"{trigger._api_url}/v1/sic/alerts/{sample_alert['uuid']}"
        mocked.get(alert_url, payload=sample_alert)

        await trigger._init_session()

        # Process alert (first occurrence)
        notification = {"alert_uuid": sample_alert["uuid"]}
        await trigger._process_alert_update(notification)

        # Should trigger immediately
        assert trigger.send_event.called
        call_args = trigger.send_event.call_args
        assert call_args[1]["event_name"] == "alert_threshold_met"
        assert call_args[1]["event"]["trigger_context"]["reason"] == "first_occurrence"

        await trigger._close_session()


@pytest.mark.asyncio
async def test_volume_threshold_trigger(config, mock_module, sample_alert, tmp_path):
    """Test that volume threshold triggers correctly."""
    trigger = AlertEventsThresholdTrigger()
    trigger.configuration = config
    trigger.module = mock_module
    trigger._data_path = tmp_path
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = AsyncMock()

    # Set internal credentials from mock module
    trigger._api_url = mock_module.configuration.base_url
    trigger._api_key = mock_module.configuration.api_key

    state_file = tmp_path / "state.json"
    trigger.state_manager = AlertStateManager(state_file)

    # Set previous state with 50 events
    trigger.state_manager.update_alert_state(
        alert_uuid=sample_alert["uuid"],
        alert_short_id=sample_alert["short_id"],
        rule_uuid=sample_alert["rule"]["uuid"],
        rule_name=sample_alert["rule"]["name"],
        event_count=50,
    )

    # Update alert to 150 events (100 new events = meets threshold)
    sample_alert["events_count"] = 150

    with aioresponses() as mocked:
        alert_url = f"{trigger._api_url}/v1/sic/alerts/{sample_alert['uuid']}"
        mocked.get(alert_url, payload=sample_alert)

        # Mock event count endpoint
        event_url = f"{trigger._api_url}/v2/events/search"
        mocked.post(event_url, payload={"total": 10})

        await trigger._init_session()

        notification = {"alert_uuid": sample_alert["uuid"]}
        await trigger._process_alert_update(notification)

        # Should trigger due to volume threshold
        assert trigger.send_event.called
        call_args = trigger.send_event.call_args
        context = call_args[1]["event"]["trigger_context"]
        assert "volume_threshold" in context["reason"]
        assert context["new_events"] == 100

        await trigger._close_session()


@pytest.mark.asyncio
async def test_below_threshold_does_not_trigger(config, mock_module, sample_alert, tmp_path):
    """Test that alerts below threshold do not trigger."""
    config.enable_time_threshold = False  # Disable time threshold for this test

    trigger = AlertEventsThresholdTrigger()
    trigger.configuration = config
    trigger.module = mock_module
    trigger._data_path = tmp_path
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = AsyncMock()

    # Set internal credentials from mock module
    trigger._api_url = mock_module.configuration.base_url
    trigger._api_key = mock_module.configuration.api_key

    state_file = tmp_path / "state.json"
    trigger.state_manager = AlertStateManager(state_file)

    # Set previous state with 100 events
    trigger.state_manager.update_alert_state(
        alert_uuid=sample_alert["uuid"],
        alert_short_id=sample_alert["short_id"],
        rule_uuid=sample_alert["rule"]["uuid"],
        rule_name=sample_alert["rule"]["name"],
        event_count=100,
    )

    # Update alert to 150 events (50 new events = below 100 threshold)
    sample_alert["events_count"] = 150

    with aioresponses() as mocked:
        alert_url = f"{trigger._api_url}/v1/sic/alerts/{sample_alert['uuid']}"
        mocked.get(alert_url, payload=sample_alert)

        await trigger._init_session()

        notification = {"alert_uuid": sample_alert["uuid"]}
        await trigger._process_alert_update(notification)

        # Should NOT trigger
        assert not trigger.send_event.called

        await trigger._close_session()


@pytest.mark.asyncio
async def test_time_threshold_trigger(config, mock_module, sample_alert, tmp_path):
    """Test that time-based threshold triggers correctly."""
    config.enable_volume_threshold = False  # Disable volume threshold for this test

    trigger = AlertEventsThresholdTrigger()
    trigger.configuration = config
    trigger.module = mock_module
    trigger._data_path = tmp_path
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = AsyncMock()

    # Set internal credentials from mock module
    trigger._api_url = mock_module.configuration.base_url
    trigger._api_key = mock_module.configuration.api_key

    state_file = tmp_path / "state.json"
    trigger.state_manager = AlertStateManager(state_file)

    # Set previous state with 100 events
    trigger.state_manager.update_alert_state(
        alert_uuid=sample_alert["uuid"],
        alert_short_id=sample_alert["short_id"],
        rule_uuid=sample_alert["rule"]["uuid"],
        rule_name=sample_alert["rule"]["name"],
        event_count=100,
    )

    # Update alert to 105 events (5 new events = below volume threshold)
    sample_alert["events_count"] = 105

    with aioresponses() as mocked:
        alert_url = f"{trigger._api_url}/v1/sic/alerts/{sample_alert['uuid']}"
        mocked.get(alert_url, payload=sample_alert)

        # Mock event count endpoint showing 3 events in last hour
        event_url = f"{trigger._api_url}/v2/events/search"
        mocked.post(event_url, payload={"total": 3})

        await trigger._init_session()

        notification = {"alert_uuid": sample_alert["uuid"]}
        await trigger._process_alert_update(notification)

        # Should trigger due to time threshold
        assert trigger.send_event.called
        call_args = trigger.send_event.call_args
        context = call_args[1]["event"]["trigger_context"]
        assert "time_threshold" in context["reason"]

        await trigger._close_session()


@pytest.mark.asyncio
async def test_rule_filter_blocks_non_matching_alerts(config, mock_module, sample_alert, tmp_path):
    """Test that rule filters block non-matching alerts."""
    config.rule_filter = "Different Rule Name"

    trigger = AlertEventsThresholdTrigger()
    trigger.configuration = config
    trigger.module = mock_module
    trigger._data_path = tmp_path
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.send_event = AsyncMock()

    # Set internal credentials from mock module
    trigger._api_url = mock_module.configuration.base_url
    trigger._api_key = mock_module.configuration.api_key

    state_file = tmp_path / "state.json"
    trigger.state_manager = AlertStateManager(state_file)

    with aioresponses() as mocked:
        alert_url = f"{trigger._api_url}/v1/sic/alerts/{sample_alert['uuid']}"
        mocked.get(alert_url, payload=sample_alert)

        await trigger._init_session()

        notification = {"alert_uuid": sample_alert["uuid"]}
        await trigger._process_alert_update(notification)

        # Should NOT trigger (filtered by rule)
        assert not trigger.send_event.called

        await trigger._close_session()


def test_state_manager_persistence(state_manager):
    """Test that state manager persists data correctly."""
    # Update state
    state_manager.update_alert_state(
        alert_uuid="test-uuid",
        alert_short_id="ALT-99999",
        rule_uuid="rule-uuid",
        rule_name="Test Rule",
        event_count=50,
    )

    # Retrieve state
    state = state_manager.get_alert_state("test-uuid")
    assert state is not None
    assert state["alert_short_id"] == "ALT-99999"
    assert state["last_triggered_event_count"] == 50
    assert state["total_triggers"] == 1

    # Update again
    state_manager.update_alert_state(
        alert_uuid="test-uuid",
        alert_short_id="ALT-99999",
        rule_uuid="rule-uuid",
        rule_name="Test Rule",
        event_count=150,
    )

    state = state_manager.get_alert_state("test-uuid")
    assert state["last_triggered_event_count"] == 150
    assert state["total_triggers"] == 2


def test_state_manager_cleanup(state_manager):
    """Test that old states are cleaned up correctly."""
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=60)

    # Create old entry
    state_manager._state["alerts"]["old-alert"] = {
        "alert_uuid": "old-alert",
        "last_triggered_at": old_date.isoformat(),
        "last_triggered_event_count": 100,
    }

    # Create recent entry
    state_manager.update_alert_state(
        alert_uuid="recent-alert",
        alert_short_id="ALT-11111",
        rule_uuid="rule-uuid",
        rule_name="Recent Rule",
        event_count=50,
    )

    # Cleanup entries older than 30 days
    cutoff = now - timedelta(days=30)
    removed = state_manager.cleanup_old_states(cutoff)

    assert removed == 1
    assert state_manager.get_alert_state("old-alert") is None
    assert state_manager.get_alert_state("recent-alert") is not None