# state_manager.py
import fcntl
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable


class AlertStateManager:
    """
    Manages persistent state for alert event thresholds.

    State structure:
    {
        "alerts": {
            "alert-uuid": {
                "alert_uuid": str,
                "alert_short_id": str,
                "rule_uuid": str,
                "rule_name": str,
                "last_triggered_at": str (ISO 8601),
                "last_triggered_event_count": int,
                "total_triggers": int,
                "created_at": str (ISO 8601),
                "updated_at": str (ISO 8601),
                "version": int,
            }
        },
        "metadata": {
            "version": str,
            "last_cleanup": str (ISO 8601),
        }
    }
    """

    VERSION = "1.0"

    def __init__(self, state_file_path: Path, logger: Optional[Callable] = None):
        """
        Initialize state manager.

        Args:
            state_file_path: Path to the state JSON file
            logger: Optional logger callable (can be a function or logger object)
        """
        self.state_file_path = Path(state_file_path)
        self.logger = logger
        self._state: dict[str, Any] = self._load_state()

    def _log(self, message: str, level: str = "info", **kwargs):
        """Helper to log using the injected logger (SDK-style)."""
        if self.logger and callable(self.logger):
            try:
                self.logger(message=message, level=level, **kwargs)
            except Exception:
                # Silently fail if logging doesn't work
                pass

    def _locked_load_state(self, file_obj):
        """Load JSON from an already locked file object."""
        file_obj.seek(0)
        try:
            state = json.load(file_obj)
            self._log("State file loaded successfully", level="debug")
        except json.JSONDecodeError as exc:
            self._log(
                "State file corrupted; starting fresh",
                level="error",
                error=str(exc),
                file_path=str(self.state_file_path),
            )
            return {
                "alerts": {},
                "metadata": {
                    "version": self.VERSION,
                    "last_cleanup": datetime.now(timezone.utc).isoformat(),
                },
            }

        # Ensure structure + version
        if state.get("metadata", {}).get("version") != self.VERSION:
            old_version = state.get("metadata", {}).get("version", "unknown")
            self._log(
                f"Migrating state from version {old_version} to {self.VERSION}",
                level="info",
                old_version=old_version,
                new_version=self.VERSION,
            )
            state = self._migrate_state(state)

        state.setdefault("alerts", {})
        state.setdefault(
            "metadata",
            {
                "version": self.VERSION,
                "last_cleanup": datetime.now(timezone.utc).isoformat(),
            },
        )
        return state

    def _locked_save_state(self, file_obj):
        """Write JSON to an already locked file object."""
        file_obj.seek(0)
        file_obj.truncate()
        json.dump(self._state, file_obj, indent=2)
        file_obj.flush()

    def _load_state(self) -> dict[str, Any]:
        """Load state from file with proper locking and error handling."""
        if not self.state_file_path.exists():
            self._log(
                "State file does not exist, creating new state", level="debug", file_path=str(self.state_file_path)
            )
            return {
                "alerts": {},
                "metadata": {
                    "version": self.VERSION,
                    "last_cleanup": datetime.now(timezone.utc).isoformat(),
                },
            }

        try:
            self._log("Loading state from file", level="debug", file_path=str(self.state_file_path))
            with open(self.state_file_path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    state = json.load(f)
                    self._log("State loaded successfully", level="debug", alert_count=len(state.get("alerts", {})))
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Migration + defaults
            if state.get("metadata", {}).get("version") != self.VERSION:
                old_version = state.get("metadata", {}).get("version", "unknown")
                self._log(
                    f"Migrating state from version {old_version} to {self.VERSION}",
                    level="info",
                    old_version=old_version,
                    new_version=self.VERSION,
                )
                state = self._migrate_state(state)
            state.setdefault("alerts", {})
            state.setdefault(
                "metadata", {"version": self.VERSION, "last_cleanup": datetime.now(timezone.utc).isoformat()}
            )
            return state
        except Exception as exc:
            self._log(
                "State file corrupted or unreadable; starting fresh",
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
                file_path=str(self.state_file_path),
            )
            return {
                "alerts": {},
                "metadata": {
                    "version": self.VERSION,
                    "last_cleanup": datetime.now(timezone.utc).isoformat(),
                },
            }

    def _save_state(self):
        """Save state to file with atomic write and locking."""
        self._log("Saving state to file", level="debug", file_path=str(self.state_file_path))

        # Create parent directory if needed
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write using temporary file + rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(self.state_file_path.parent),
            prefix=".tmp_state_",
            suffix=".json",
        )

        try:
            # open by fd to ensure correct handle is locked
            with open(temp_fd, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                try:
                    json.dump(self._state, f, indent=2)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            Path(temp_path).rename(self.state_file_path)
            self._log(
                "State saved successfully",
                level="debug",
                file_path=str(self.state_file_path),
                alert_count=len(self._state.get("alerts", {})),
            )
        except Exception as e:
            # Clean up temp file on error
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            self._log(
                "Failed to save state file",
                level="error",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(self.state_file_path),
            )
            raise

    def _migrate_state(self, old_state: dict[str, Any]) -> dict[str, Any]:
        """Migrate state from older versions. Currently a no-op (placeholder)."""
        # Future: implement version migrations here
        old_state.setdefault("alerts", {})
        old_state.setdefault(
            "metadata", {"version": self.VERSION, "last_cleanup": datetime.now(timezone.utc).isoformat()}
        )
        return old_state

    def get_alert_state(self, alert_uuid: str) -> Optional[dict[str, Any]]:
        """
        Get state for a specific alert.

        Args:
            alert_uuid: UUID of the alert

        Returns:
            Alert state dictionary or None if not found
        """
        state = self._state["alerts"].get(alert_uuid)
        if state:
            self._log(
                f"Retrieved state for alert {alert_uuid}",
                level="debug",
                alert_uuid=alert_uuid,
                last_triggered_count=state.get("last_triggered_event_count"),
                total_triggers=state.get("total_triggers"),
            )
        else:
            self._log(f"No state found for alert {alert_uuid}", level="debug", alert_uuid=alert_uuid)
        return state

    def update_alert_state(
        self,
        alert_uuid: str,
        alert_short_id: str,
        rule_uuid: str,
        rule_name: str,
        event_count: int,
        previous_version: Optional[int] = None,
    ):
        """
        Update the state for a specific alert with full file locking.

        Args:
            alert_uuid: UUID of the alert
            alert_short_id: Short ID of the alert
            rule_uuid: UUID of the rule
            rule_name: Name of the rule
            event_count: Current event count
            previous_version: Expected version for optimistic locking (unused for now)
        """
        self._log(
            f"Updating state for alert {alert_short_id}",
            level="debug",
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            event_count=event_count,
        )
        now = datetime.now(timezone.utc).isoformat()

        # Ensure state file exists before opening
        if not self.state_file_path.exists():
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_file_path.write_text(
                json.dumps(
                    {
                        "alerts": {},
                        "metadata": {
                            "version": self.VERSION,
                            "last_cleanup": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                )
            )

        # FULL FILE LOCK OVER THE ENTIRE READ → MODIFY → WRITE
        with open(self.state_file_path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                # load fresh state from file
                self._state = self._locked_load_state(f)

                existing = self._state["alerts"].get(alert_uuid)

                if existing:
                    current_version = existing.get("version", 0)
                    existing.update(
                        {
                            "alert_short_id": alert_short_id,
                            "rule_uuid": rule_uuid,
                            "rule_name": rule_name,
                            "last_triggered_at": now,
                            "last_triggered_event_count": event_count,
                            "total_triggers": existing.get("total_triggers", 0) + 1,
                            "updated_at": now,
                            "version": current_version + 1,
                        }
                    )
                    self._log(
                        f"Updated existing state for alert {alert_short_id}",
                        level="debug",
                        alert_uuid=alert_uuid,
                        new_version=current_version + 1,
                        total_triggers=existing["total_triggers"],
                    )
                else:
                    self._state["alerts"][alert_uuid] = {
                        "alert_uuid": alert_uuid,
                        "alert_short_id": alert_short_id,
                        "rule_uuid": rule_uuid,
                        "rule_name": rule_name,
                        "last_triggered_at": now,
                        "last_triggered_event_count": event_count,
                        "total_triggers": 1,
                        "created_at": now,
                        "updated_at": now,
                        "version": 1,
                    }
                    self._log(f"Created new state for alert {alert_short_id}", level="debug", alert_uuid=alert_uuid)

                # save back
                self._locked_save_state(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def cleanup_old_states(self, cutoff_date: datetime) -> int:
        """
        Remove state entries for alerts not triggered since cutoff date.

        Args:
            cutoff_date: Remove entries older than this date

        Returns:
            Number of entries removed
        """
        self._log(
            "Starting cleanup of old states",
            level="debug",
            cutoff_date=cutoff_date.isoformat(),
            total_states=len(self._state["alerts"]),
        )

        # Ensure state file exists before opening
        if not self.state_file_path.exists():
            self._log("State file does not exist, nothing to cleanup", level="debug")
            return 0

        # FULL FILE LOCK OVER THE ENTIRE READ → MODIFY → WRITE
        with open(self.state_file_path, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                # load fresh state from file
                self._state = self._locked_load_state(f)

                cutoff_iso = cutoff_date.isoformat()
                to_remove = []

                # FIX: Compare using string comparison (ISO format is lexicographically sortable)
                for alert_uuid, state in list(self._state["alerts"].items()):
                    last_triggered = state.get("last_triggered_at", "")
                    # If last_triggered is earlier than cutoff, remove it
                    if last_triggered and last_triggered < cutoff_iso:
                        to_remove.append(alert_uuid)
                        self._log(
                            f"Marking alert {state.get('alert_short_id')} for removal",
                            level="debug",
                            alert_uuid=alert_uuid,
                            last_triggered_at=last_triggered,
                        )

                for alert_uuid in to_remove:
                    del self._state["alerts"][alert_uuid]

                if to_remove:
                    self._state["metadata"]["last_cleanup"] = datetime.now(timezone.utc).isoformat()
                    # save back with lock
                    self._locked_save_state(f)
                    self._log(
                        f"Cleanup completed: removed {len(to_remove)} old states",
                        level="info",
                        removed_count=len(to_remove),
                        remaining_count=len(self._state["alerts"]),
                    )
                else:
                    self._log("Cleanup completed: no old states to remove", level="debug")

                return len(to_remove)
            except Exception as e:
                self._log(
                    "Error during cleanup of old states",
                    level="error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the current state.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_alerts": len(self._state["alerts"]),
            "version": self._state["metadata"]["version"],
            "last_cleanup": self._state["metadata"]["last_cleanup"],
        }
