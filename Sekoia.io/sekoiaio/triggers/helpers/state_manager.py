# state_manager.py
import json
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any


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
                # New fields for optimizations:
                "alert_info": dict (cached alert data from API/notification),
                "current_event_count": int (latest known event count),
                "last_event_at": str (ISO 8601, timestamp of last event received),
            }
        },
        "metadata": {
            "version": str,
            "last_cleanup": str (ISO 8601),
        }
    }
    """

    VERSION = "1.1"

    def __init__(self, state_file_path: Path, logger: Callable | None = None):
        """
        Initialize state manager.

        Args:
            state_file_path: Path to the state JSON file (can be S3Path or PosixPath)
            logger: Optional logger callable (can be a function or logger object)
        """
        # Keep the original path object (S3Path, PosixPath, etc.) to preserve S3 functionality
        self.state_file_path = state_file_path
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

    def _load_state_from_s3(self) -> dict[str, Any]:
        """Load JSON from S3 using Path.open() for SDK compatibility."""
        try:
            # Use Path.open() instead of smart_open for SDK-managed paths
            with self.state_file_path.open("r") as f:
                state = json.load(f)
                self._log("State file loaded successfully from S3", level="debug")
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
        except (FileNotFoundError, IOError, OSError) as exc:
            # Handle both standard file errors and S3-specific errors (404, etc.)
            self._log(
                "State file not found or inaccessible in S3, creating new state",
                level="debug",
                error=str(exc),
                error_type=type(exc).__name__,
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

    def _save_state_to_s3(self):
        """Write JSON to S3 using Path.open() for SDK compatibility."""
        try:
            # Ensure parent directory exists - required for S3Path (see SDK storage.py)
            # This pattern is used in all other automation modules
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Use Path.open() for SDK-managed S3 paths
            with self.state_file_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
            self._log("State saved successfully to S3", level="debug")
        except Exception as e:
            self._log(
                "Failed to save state to S3",
                level="error",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(self.state_file_path),
            )
            raise

    def _load_state(self) -> dict[str, Any]:
        """Load state from S3."""
        self._log("Loading state from S3", level="debug", file_path=str(self.state_file_path))
        try:
            return self._load_state_from_s3()
        except Exception as exc:
            self._log(
                "Failed to load state from S3, starting with fresh state",
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
        """Save state to S3. Logging is handled by _save_state_to_s3."""
        self._save_state_to_s3()

    def _migrate_state(self, old_state: dict[str, Any]) -> dict[str, Any]:
        """
        Migrate state from older versions.

        Migration from v1.0 to v1.1:
        - Adds 'alert_info' field (cached alert data, default: None)
        - Adds 'current_event_count' field (latest known count, default: last_triggered_event_count)
        - Adds 'last_event_at' field (timestamp of last event, default: None)
        """
        old_state.setdefault("alerts", {})
        old_state.setdefault(
            "metadata", {"version": self.VERSION, "last_cleanup": datetime.now(timezone.utc).isoformat()}
        )

        # Migrate each alert entry to add new fields (v1.0 -> v1.1)
        for alert_uuid, alert_state in old_state.get("alerts", {}).items():
            # Initialize 'alert_info' if not present (v1.1 field)
            if "alert_info" not in alert_state:
                alert_state["alert_info"] = None

            # Initialize 'current_event_count' if not present (v1.1 field)
            # Default to last_triggered_event_count for backwards compatibility
            if "current_event_count" not in alert_state:
                alert_state["current_event_count"] = alert_state.get("last_triggered_event_count", 0)

            # Initialize 'last_event_at' if not present (v1.1 field)
            if "last_event_at" not in alert_state:
                alert_state["last_event_at"] = None

            self._log(
                f"Migrated alert state for {alert_uuid}",
                level="debug",
                alert_uuid=alert_uuid,
            )

        # Update version in metadata
        old_state["metadata"]["version"] = self.VERSION

        return old_state

    def get_alert_state(self, alert_uuid: str) -> dict[str, Any] | None:
        """Get state for a specific alert, or None if not found."""
        return self._state["alerts"].get(alert_uuid)

    def update_alert_state(
        self,
        alert_uuid: str,
        alert_short_id: str,
        rule_uuid: str,
        rule_name: str,
        event_count: int,
    ):
        """
        Update the state for a specific alert and persist to storage.

        The caller is responsible for calling reload_state() beforehand
        if fresh state from S3 is needed.

        Args:
            alert_uuid: UUID of the alert
            alert_short_id: Short ID of the alert
            rule_uuid: UUID of the rule
            rule_name: Name of the rule
            event_count: Current event count
        """
        now = datetime.now(timezone.utc).isoformat()

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

        # Save back to S3
        self._save_state_to_s3()

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

        try:
            cutoff_iso = cutoff_date.isoformat()
            to_remove = []

            # Compare using string comparison (ISO format is lexicographically sortable)
            for alert_uuid, state in list(self._state["alerts"].items()):
                last_triggered = state.get("last_triggered_at")
                # For never-triggered alerts, use created_at or updated_at as reference
                if not last_triggered:
                    last_triggered = state.get("created_at") or state.get("updated_at")
                # If reference timestamp is earlier than cutoff, remove it
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
                # save back to S3
                self._save_state_to_s3()
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

    def update_alert_info(
        self,
        alert_uuid: str,
        alert_info: dict[str, Any],
        event_count: int,
    ):
        """
        Update cached alert info and current event count (without triggering).
        Used to store alert data from notifications to avoid API calls.

        The caller is responsible for calling reload_state() beforehand
        if fresh state from S3 is needed.

        Args:
            alert_uuid: UUID of the alert
            alert_info: Alert data to cache (from notification or API)
            event_count: Current event count from notification
        """
        now = datetime.now(timezone.utc).isoformat()

        existing = self._state["alerts"].get(alert_uuid)

        if existing:
            existing.update(
                {
                    "alert_info": alert_info,
                    "current_event_count": event_count,
                    "last_event_at": now,
                    "updated_at": now,
                }
            )
        else:
            # Create new state entry with alert info but no trigger yet
            self._state["alerts"][alert_uuid] = {
                "alert_uuid": alert_uuid,
                "alert_short_id": alert_info.get("short_id", ""),
                "rule_uuid": alert_info.get("rule", {}).get("uuid", ""),
                "rule_name": alert_info.get("rule", {}).get("name", ""),
                "last_triggered_at": None,
                "last_triggered_event_count": 0,
                "total_triggers": 0,
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "alert_info": alert_info,
                "current_event_count": event_count,
                "last_event_at": now,
            }
        self._save_state_to_s3()

    def get_alert_info(self, alert_uuid: str) -> dict[str, Any] | None:
        """Get cached alert info for a specific alert, or None if not found."""
        state = self._state["alerts"].get(alert_uuid)
        if state:
            return state.get("alert_info")
        return None

    def get_alerts_pending_time_check(self, time_window_hours: int) -> list[dict[str, Any]]:
        """
        Get alerts that have pending events and the time window has elapsed since last trigger.
        Used for periodic time threshold checking.

        The time threshold logic:
        - If never triggered: check if time_window_hours has passed since the first event
        - If previously triggered: check if time_window_hours has passed since last trigger
        - Only return alerts with pending events (current_count > last_triggered_count)

        Args:
            time_window_hours: Time window in hours (1-168)

        Returns:
            List of alert states that need time threshold triggering
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        required_duration = timedelta(hours=time_window_hours)
        pending_alerts: list[dict[str, Any]] = []

        for alert_uuid, state in self._state["alerts"].items():
            # Skip if no events received yet
            if not state.get("last_event_at"):
                continue

            # Skip if no pending events
            pending = state.get("current_event_count", 0) - state.get("last_triggered_event_count", 0)
            if pending <= 0:
                continue

            # Determine reference time: last trigger or creation
            reference_str = state.get("last_triggered_at") or state.get("created_at") or state.get("last_event_at")
            try:
                reference_time = datetime.fromisoformat(reference_str.replace("Z", "+00:00"))
                if reference_time.tzinfo is None:
                    reference_time = reference_time.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError, TypeError):
                self._log(f"Invalid timestamp for alert {alert_uuid}", level="warning")
                continue

            if (now - reference_time) >= required_duration:
                pending_alerts.append(state)

        return pending_alerts

    def get_all_alerts(self) -> dict[str, dict[str, Any]]:
        """
        Get all alert states.

        Returns:
            Dictionary of all alert states
        """
        return self._state["alerts"].copy()

    def reload_state(self):
        """
        Reload state from storage (S3 or local file).

        This is useful when you need to get the latest state from storage,
        for example in periodic background tasks.

        Concurrency model:
        - This class uses a single-writer model: one trigger instance owns the state
        - In-memory state may become stale immediately after reload if another process
          writes to S3 concurrently (eventual consistency)
        - For multi-instance deployments, external coordination (e.g., locks) should be used
        - The current implementation is designed for single-instance deployments where
          one trigger process handles all notifications for a given configuration
        """
        self._state = self._load_state()
        self._log("State reloaded from storage", level="debug")
