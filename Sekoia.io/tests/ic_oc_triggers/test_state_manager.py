from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sekoiaio.triggers.helpers.state_manager import AlertStateManager


@pytest.fixture
def mock_logger():
    """Mock logger function for tests."""
    return Mock()


@pytest.fixture
def state_file_path(tmp_path):
    """Temporary state file path for tests."""
    return tmp_path / "test_state.json"


@pytest.fixture
def state_manager(state_file_path, mock_logger):
    """Create AlertStateManager instance for tests."""
    return AlertStateManager(state_file_path, logger=mock_logger)


class TestAlertStateManager:
    def test_init_creates_empty_state(self, state_manager):
        """Test that initialization creates empty state structure."""
        assert "alerts" in state_manager._state
        assert "metadata" in state_manager._state
        assert state_manager._state["metadata"]["version"] == "1.0"
        assert len(state_manager._state["alerts"]) == 0

    def test_load_state_from_nonexistent_file(self, state_file_path, mock_logger):
        """Test loading state when file doesn't exist."""
        manager = AlertStateManager(state_file_path, logger=mock_logger)

        assert manager._state["alerts"] == {}
        assert manager._state["metadata"]["version"] == "1.0"

    def test_load_state_with_corrupted_json(self, state_file_path, mock_logger):
        """Test loading state with corrupted JSON file."""
        # Create a corrupted JSON file
        state_file_path.write_text("{invalid json")

        manager = AlertStateManager(state_file_path, logger=mock_logger)

        # Should start with fresh state
        assert manager._state["alerts"] == {}
        assert manager._state["metadata"]["version"] == "1.0"
        # Should log error
        mock_logger.assert_called()

    def test_get_alert_state_existing(self, state_manager):
        """Test getting state for existing alert."""
        alert_uuid = "test-alert-123"
        state_manager._state["alerts"][alert_uuid] = {
            "alert_uuid": alert_uuid,
            "alert_short_id": "AL123",
            "last_triggered_event_count": 10,
            "total_triggers": 2,
        }

        result = state_manager.get_alert_state(alert_uuid)

        assert result is not None
        assert result["alert_uuid"] == alert_uuid
        assert result["last_triggered_event_count"] == 10

    def test_get_alert_state_nonexistent(self, state_manager):
        """Test getting state for non-existent alert."""
        result = state_manager.get_alert_state("nonexistent-uuid")
        assert result is None

    def test_update_alert_state_new_alert(self, state_manager):
        """Test updating state for a new alert."""
        alert_uuid = "new-alert-456"
        alert_short_id = "AL456"
        rule_uuid = "rule-789"
        rule_name = "Test Rule"
        event_count = 5

        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid=rule_uuid,
            rule_name=rule_name,
            event_count=event_count,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state is not None
        assert state["alert_uuid"] == alert_uuid
        assert state["alert_short_id"] == alert_short_id
        assert state["rule_uuid"] == rule_uuid
        assert state["rule_name"] == rule_name
        assert state["last_triggered_event_count"] == event_count
        assert state["total_triggers"] == 1
        assert state["version"] == 1

    def test_update_alert_state_existing_alert(self, state_manager):
        """Test updating state for an existing alert."""
        alert_uuid = "existing-alert-789"
        alert_short_id = "AL789"

        # Create initial state
        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid="rule-1",
            rule_name="Rule 1",
            event_count=5,
        )

        # Update state
        state_manager.update_alert_state(
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            rule_uuid="rule-1",
            rule_name="Rule 1",
            event_count=15,
        )

        state = state_manager.get_alert_state(alert_uuid)
        assert state["last_triggered_event_count"] == 15
        assert state["total_triggers"] == 2
        assert state["version"] == 2

    def test_cleanup_old_states_removes_old_alerts(self, state_manager):
        """Test cleanup removes alerts older than cutoff date."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=35)

        # Add old alert using update_alert_state to ensure it's persisted
        state_manager._state["alerts"]["old-alert"] = {
            "alert_uuid": "old-alert",
            "alert_short_id": "AL_OLD",
            "last_triggered_at": old_date.isoformat(),
        }
        state_manager._save_state()

        # Add recent alert
        state_manager._state["alerts"]["recent-alert"] = {
            "alert_uuid": "recent-alert",
            "alert_short_id": "AL_RECENT",
            "last_triggered_at": now.isoformat(),
        }
        state_manager._save_state()

        cutoff_date = now - timedelta(days=30)
        removed = state_manager.cleanup_old_states(cutoff_date)

        assert removed == 1
        assert "old-alert" not in state_manager._state["alerts"]
        assert "recent-alert" in state_manager._state["alerts"]

    def test_cleanup_old_states_no_old_alerts(self, state_manager):
        """Test cleanup when there are no old alerts."""
        now = datetime.now(timezone.utc)

        # Add only recent alert using update_alert_state to ensure it's persisted
        state_manager._state["alerts"]["recent-alert"] = {
            "alert_uuid": "recent-alert",
            "alert_short_id": "AL_RECENT",
            "last_triggered_at": now.isoformat(),
        }
        state_manager._save_state()

        cutoff_date = now - timedelta(days=30)
        removed = state_manager.cleanup_old_states(cutoff_date)

        assert removed == 0
        assert "recent-alert" in state_manager._state["alerts"]

    def test_get_stats(self, state_manager):
        """Test getting statistics."""
        # Add some alerts
        state_manager._state["alerts"]["alert1"] = {"alert_uuid": "alert1"}
        state_manager._state["alerts"]["alert2"] = {"alert_uuid": "alert2"}
        state_manager._state["alerts"]["alert3"] = {"alert_uuid": "alert3"}

        stats = state_manager.get_stats()

        assert stats["total_alerts"] == 3
        assert stats["version"] == "1.0"
        assert "last_cleanup" in stats

    def test_save_and_load_state_persistence(self, state_file_path, mock_logger):
        """Test that state persists across manager instances."""
        # Create first manager and add state
        manager1 = AlertStateManager(state_file_path, logger=mock_logger)
        manager1.update_alert_state(
            alert_uuid="persist-test",
            alert_short_id="AL_PERSIST",
            rule_uuid="rule-persist",
            rule_name="Persist Rule",
            event_count=42,
        )

        # Create second manager with same file
        manager2 = AlertStateManager(state_file_path, logger=mock_logger)

        # Verify state was loaded
        state = manager2.get_alert_state("persist-test")
        assert state is not None
        assert state["alert_short_id"] == "AL_PERSIST"
        assert state["last_triggered_event_count"] == 42

    def test_logger_failure_silently_handled(self, state_file_path):
        """Test that logger failures don't crash the manager."""
        failing_logger = Mock(side_effect=Exception("Logger failed"))

        # Should not raise exception despite logger failure
        manager = AlertStateManager(state_file_path, logger=failing_logger)

        # Operations should still work
        manager.update_alert_state(
            alert_uuid="test",
            alert_short_id="AL_TEST",
            rule_uuid="rule",
            rule_name="Rule",
            event_count=1,
        )

        state = manager.get_alert_state("test")
        assert state is not None

    def test_migrate_state_maintains_structure(self, state_manager):
        """Test that state migration maintains required structure."""
        old_state = {"alerts": {"old": {}}}

        migrated = state_manager._migrate_state(old_state)

        assert "alerts" in migrated
        assert "metadata" in migrated
        assert migrated["metadata"]["version"] == "1.0"

    def test_update_alert_state_with_ioerror(self, state_file_path, mock_logger):
        """Test handling of IOError during state update."""
        manager = AlertStateManager(state_file_path, logger=mock_logger)

        # Mock Path.open to raise IOError on write
        with patch.object(Path, "open", side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                manager.update_alert_state(
                    alert_uuid="test",
                    alert_short_id="AL_TEST",
                    rule_uuid="rule",
                    rule_name="Rule",
                    event_count=1,
                )

            # Verify error was logged
            assert mock_logger.called
            # Check that logger was called with error level and appropriate message
            log_calls = [str(call) for call in mock_logger.call_args_list]
            assert any("error" in call.lower() or "failed" in call.lower() for call in log_calls)

    def test_cleanup_with_exception_propagates(self, state_manager):
        """Test that exceptions during cleanup are propagated."""
        # Mock _load_state to raise exception
        with patch.object(state_manager, "_load_state", side_effect=Exception("Load failed")):
            with pytest.raises(Exception, match="Load failed"):
                state_manager.cleanup_old_states(datetime.now(timezone.utc))
