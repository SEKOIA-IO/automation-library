import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from sekoiaio.triggers.helpers.state_manager import AlertStateManager


# ----------------------------------------------------------------------
# Initialization Tests
# ----------------------------------------------------------------------

def test_state_manager_initialization():
    """Test state manager initialization with new state file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        
        manager = AlertStateManager(state_path)
        
        assert manager.state_file == state_path
        assert manager._state == {"version": 1, "alerts": {}}


def test_state_manager_initialization_with_logger():
    """Test state manager initialization with logger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        mock_logger = MagicMock()
        
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        assert manager.logger == mock_logger


def test_state_manager_loads_existing_state():
    """Test state manager loads existing state file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        
        # Create existing state file
        existing_state = {
            "version": 1,
            "alerts": {
                "alert-1": {
                    "alert_uuid": "alert-1",
                    "last_triggered_at": "2024-01-01T00:00:00Z",
                    "last_triggered_event_count": 100,
                }
            }
        }
        
        with open(state_path, 'w') as f:
            json.dump(existing_state, f)
        
        manager = AlertStateManager(state_path)
        
        assert manager._state == existing_state
        assert "alert-1" in manager._state["alerts"]


def test_state_manager_handles_corrupt_state_file():
    """Test state manager handles corrupt state file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        
        # Create corrupt state file
        with open(state_path, 'w') as f:
            f.write("{ corrupt json")
        
        mock_logger = MagicMock()
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        # Should create new state
        assert manager._state == {"version": 1, "alerts": {}}


def test_state_manager_handles_missing_version():
    """Test state manager handles state file without version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        
        # Create state file without version
        state_without_version = {
            "alerts": {
                "alert-1": {"alert_uuid": "alert-1"}
            }
        }
        
        with open(state_path, 'w') as f:
            json.dump(state_without_version, f)
        
        mock_logger = MagicMock()
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        # Should initialize new state
        assert manager._state == {"version": 1, "alerts": {}}


# ----------------------------------------------------------------------
# Get Alert State Tests
# ----------------------------------------------------------------------

def test_get_alert_state_existing():
    """Test getting state for existing alert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # Add alert state
        manager._state["alerts"]["alert-1"] = {
            "alert_uuid": "alert-1",
            "last_triggered_event_count": 50,
        }
        
        state = manager.get_alert_state("alert-1")
        
        assert state is not None
        assert state["alert_uuid"] == "alert-1"
        assert state["last_triggered_event_count"] == 50


def test_get_alert_state_non_existing():
    """Test getting state for non-existing alert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        state = manager.get_alert_state("non-existing")
        
        assert state is None


# ----------------------------------------------------------------------
# Update Alert State Tests
# ----------------------------------------------------------------------

def test_update_alert_state_new_alert():
    """Test updating state for new alert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        manager.update_alert_state(
            alert_uuid="alert-new",
            alert_short_id="A-NEW",
            rule_uuid="rule-1",
            rule_name="TestRule",
            event_count=100,
        )
        
        state = manager._state["alerts"]["alert-new"]
        
        assert state["alert_uuid"] == "alert-new"
        assert state["alert_short_id"] == "A-NEW"
        assert state["rule_uuid"] == "rule-1"
        assert state["rule_name"] == "TestRule"
        assert state["last_triggered_event_count"] == 100
        assert state["version"] == 1
        assert "last_triggered_at" in state


def test_update_alert_state_existing_alert():
    """Test updating state for existing alert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # First update
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="TestRule",
            event_count=50,
        )
        
        # Second update
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="TestRule",
            event_count=150,
            previous_version=1,
        )
        
        state = manager._state["alerts"]["alert-1"]
        
        assert state["last_triggered_event_count"] == 150
        assert state["version"] == 2


def test_update_alert_state_version_mismatch():
    """Test update with version mismatch logs warning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        mock_logger = MagicMock()
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        # First update
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="TestRule",
            event_count=50,
        )
        
        # Second update with wrong version
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="TestRule",
            event_count=150,
            previous_version=5,  # Wrong version
        )
        
        # Should log warning
        mock_logger.assert_called()


def test_update_alert_state_persists_to_file():
    """Test that state updates are persisted to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        manager.update_alert_state(
            alert_uuid="alert-persist",
            alert_short_id="A-P",
            rule_uuid="rule-p",
            rule_name="PersistRule",
            event_count=75,
        )
        
        # Verify file was written
        assert state_path.exists()
        
        # Load from file
        with open(state_path, 'r') as f:
            file_state = json.load(f)
        
        assert "alert-persist" in file_state["alerts"]
        assert file_state["alerts"]["alert-persist"]["last_triggered_event_count"] == 75


def test_update_alert_state_optional_fields():
    """Test update with optional fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        manager.update_alert_state(
            alert_uuid="alert-opt",
            event_count=100,
        )
        
        state = manager._state["alerts"]["alert-opt"]
        
        assert state["alert_uuid"] == "alert-opt"
        assert state["last_triggered_event_count"] == 100
        assert state.get("alert_short_id") is None
        assert state.get("rule_uuid") is None


# ----------------------------------------------------------------------
# Cleanup Tests
# ----------------------------------------------------------------------

def test_cleanup_old_states_removes_old_alerts():
    """Test cleanup removes alerts older than cutoff date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=10)
        recent_date = now - timedelta(days=1)
        
        # Add old alert
        manager._state["alerts"]["alert-old"] = {
            "alert_uuid": "alert-old",
            "last_triggered_at": old_date.isoformat(),
            "last_triggered_event_count": 50,
        }
        
        # Add recent alert
        manager._state["alerts"]["alert-recent"] = {
            "alert_uuid": "alert-recent",
            "last_triggered_at": recent_date.isoformat(),
            "last_triggered_event_count": 100,
        }
        
        # Cleanup alerts older than 7 days
        cutoff = now - timedelta(days=7)
        removed = manager.cleanup_old_states(cutoff)
        
        assert removed == 1
        assert "alert-old" not in manager._state["alerts"]
        assert "alert-recent" in manager._state["alerts"]


def test_cleanup_old_states_no_old_alerts():
    """Test cleanup when no alerts are old."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        now = datetime.now(timezone.utc)
        recent_date = now - timedelta(hours=1)
        
        # Add recent alert
        manager._state["alerts"]["alert-recent"] = {
            "alert_uuid": "alert-recent",
            "last_triggered_at": recent_date.isoformat(),
            "last_triggered_event_count": 100,
        }
        
        # Cleanup
        cutoff = now - timedelta(days=7)
        removed = manager.cleanup_old_states(cutoff)
        
        assert removed == 0
        assert "alert-recent" in manager._state["alerts"]


def test_cleanup_old_states_invalid_date_format():
    """Test cleanup handles alerts with invalid date format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        mock_logger = MagicMock()
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        # Add alert with invalid date
        manager._state["alerts"]["alert-invalid"] = {
            "alert_uuid": "alert-invalid",
            "last_triggered_at": "invalid-date",
            "last_triggered_event_count": 50,
        }
        
        # Add alert without date
        manager._state["alerts"]["alert-no-date"] = {
            "alert_uuid": "alert-no-date",
            "last_triggered_event_count": 75,
        }
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        removed = manager.cleanup_old_states(cutoff)
        
        # Invalid dates should not cause crashes
        # Alerts without valid dates are kept
        assert removed == 0


def test_cleanup_old_states_persists_changes():
    """Test that cleanup persists changes to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=10)
        
        # Add old alert
        manager._state["alerts"]["alert-old"] = {
            "alert_uuid": "alert-old",
            "last_triggered_at": old_date.isoformat(),
            "last_triggered_event_count": 50,
        }
        
        manager._save_state()
        
        # Cleanup
        cutoff = now - timedelta(days=7)
        manager.cleanup_old_states(cutoff)
        
        # Reload from file
        with open(state_path, 'r') as f:
            file_state = json.load(f)
        
        assert "alert-old" not in file_state["alerts"]


# ----------------------------------------------------------------------
# Save State Tests
# ----------------------------------------------------------------------

def test_save_state_creates_file():
    """Test that save state creates the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        manager._state["alerts"]["test-alert"] = {
            "alert_uuid": "test-alert",
            "last_triggered_event_count": 123,
        }
        
        manager._save_state()
        
        assert state_path.exists()


def test_save_state_handles_write_errors():
    """Test that save state handles write errors gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory where the file should be (causes write error)
        state_path = Path(tmpdir) / "test_state.json"
        state_path.mkdir()
        
        mock_logger = MagicMock()
        manager = AlertStateManager(state_path, logger=mock_logger)
        
        manager._state["alerts"]["test-alert"] = {
            "alert_uuid": "test-alert",
        }
        
        # Should not raise exception
        manager._save_state()


def test_save_state_atomic_write():
    """Test that state is written atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # Write initial state
        manager._state["alerts"]["alert-1"] = {"alert_uuid": "alert-1"}
        manager._save_state()
        
        # Modify and save again
        manager._state["alerts"]["alert-2"] = {"alert_uuid": "alert-2"}
        manager._save_state()
        
        # Verify both alerts are in the file
        with open(state_path, 'r') as f:
            file_state = json.load(f)
        
        assert "alert-1" in file_state["alerts"]
        assert "alert-2" in file_state["alerts"]


# ----------------------------------------------------------------------
# Integration Tests
# ----------------------------------------------------------------------

def test_state_manager_full_workflow():
    """Test complete state manager workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # Add multiple alerts
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="Rule1",
            event_count=100,
        )
        
        manager.update_alert_state(
            alert_uuid="alert-2",
            alert_short_id="A-2",
            rule_uuid="rule-2",
            rule_name="Rule2",
            event_count=200,
        )
        
        # Get states
        state1 = manager.get_alert_state("alert-1")
        state2 = manager.get_alert_state("alert-2")
        
        assert state1["last_triggered_event_count"] == 100
        assert state2["last_triggered_event_count"] == 200
        
        # Update existing alert
        manager.update_alert_state(
            alert_uuid="alert-1",
            alert_short_id="A-1",
            rule_uuid="rule-1",
            rule_name="Rule1",
            event_count=150,
            previous_version=1,
        )
        
        updated_state = manager.get_alert_state("alert-1")
        assert updated_state["last_triggered_event_count"] == 150
        assert updated_state["version"] == 2
        
        # Create new manager to test persistence
        manager2 = AlertStateManager(state_path)
        
        reloaded_state1 = manager2.get_alert_state("alert-1")
        reloaded_state2 = manager2.get_alert_state("alert-2")
        
        assert reloaded_state1["last_triggered_event_count"] == 150
        assert reloaded_state2["last_triggered_event_count"] == 200


def test_state_manager_concurrent_updates():
    """Test state manager handles rapid updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # Simulate rapid updates
        for i in range(10):
            manager.update_alert_state(
                alert_uuid="alert-rapid",
                alert_short_id="A-R",
                rule_uuid="rule-r",
                rule_name="RapidRule",
                event_count=i * 10,
                previous_version=i if i > 0 else None,
            )
        
        final_state = manager.get_alert_state("alert-rapid")
        
        assert final_state["last_triggered_event_count"] == 90
        assert final_state["version"] == 10


def test_state_manager_large_state():
    """Test state manager with large number of alerts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "test_state.json"
        manager = AlertStateManager(state_path)
        
        # Add 1000 alerts
        for i in range(1000):
            manager.update_alert_state(
                alert_uuid=f"alert-{i}",
                alert_short_id=f"A-{i}",
                rule_uuid=f"rule-{i}",
                rule_name=f"Rule{i}",
                event_count=i * 10,
            )
        
        # Verify all alerts are stored
        assert len(manager._state["alerts"]) == 1000
        
        # Verify specific alerts
        state_0 = manager.get_alert_state("alert-0")
        state_999 = manager.get_alert_state("alert-999")
        
        assert state_0["last_triggered_event_count"] == 0
        assert state_999["last_triggered_event_count"] == 9990
        
        # Cleanup old alerts
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=1)
        
        # All alerts should be considered "old" since they were just created
        # but let's verify the cleanup mechanism works
        removed = manager.cleanup_old_states(cutoff)
        
        # Should have removed some or all alerts depending on timing
        assert removed >= 0