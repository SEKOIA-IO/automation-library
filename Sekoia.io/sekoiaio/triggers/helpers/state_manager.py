# state_manager.py
import json
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

    def __init__(self, state_file_path: Path, logger: Optional[Callable] = None):
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
        """Save state to S3."""
        self._log("Saving state to S3", level="debug", file_path=str(self.state_file_path))
        try:
            self._save_state_to_s3()
            self._log(
                "State saved successfully",
                level="debug",
                file_path=str(self.state_file_path),
                alert_count=len(self._state.get("alerts", {})),
            )
        except Exception as e:
            self._log(
                "Failed to save state to S3",
                level="error",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(self.state_file_path),
            )
            raise

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
        Update the state for a specific alert.

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

        # Reload state from S3 to get latest version (use _load_state for consistent error handling)
        self._state = self._load_state()

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
            # Reload state from S3 to get latest version (use _load_state for consistent error handling)
            self._state = self._load_state()

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

        Note: This method reloads state from S3 on each call to ensure consistency.
        While this adds latency per notification, it ensures we don't lose updates
        from other processes. For high-volume scenarios, consider implementing
        a write-through cache or batching updates.

        Args:
            alert_uuid: UUID of the alert
            alert_info: Alert data to cache (from notification or API)
            event_count: Current event count from notification
        """
        now = datetime.now(timezone.utc).isoformat()

        # Reload state from S3 to get latest version before updating
        # This ensures consistency when multiple processes may be updating
        self._state = self._load_state()

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
            self._log(
                f"Updated alert info cache for {alert_uuid}",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=event_count,
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
            self._log(
                f"Created new alert info cache for {alert_uuid}",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=event_count,
            )

        # Save back to S3
        self._save_state_to_s3()

    def get_alert_info(self, alert_uuid: str) -> Optional[dict[str, Any]]:
        """
        Get cached alert info for a specific alert.

        Args:
            alert_uuid: UUID of the alert

        Returns:
            Cached alert info dictionary or None if not found
        """
        state = self._state["alerts"].get(alert_uuid)
        if state and state.get("alert_info"):
            self._log(
                f"Retrieved cached alert info for {alert_uuid}",
                level="debug",
                alert_uuid=alert_uuid,
            )
            return state.get("alert_info")
        return None

    def get_alerts_pending_time_check(self, time_window_hours: int) -> list[dict[str, Any]]:
        """
        Get alerts that have pending events within the time window and haven't been triggered yet.
        Used for periodic time threshold checking.

        Args:
            time_window_hours: Time window in hours (1-168)

        Returns:
            List of alert states that need time threshold evaluation
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=time_window_hours)

        pending_alerts = []
        for alert_uuid, state in self._state["alerts"].items():
            last_event_at_str = state.get("last_event_at")
            last_triggered_at_str = state.get("last_triggered_at")
            current_count = state.get("current_event_count", 0)
            last_triggered_count = state.get("last_triggered_event_count", 0)

            # Skip if no events received yet
            if not last_event_at_str:
                continue

            # Check if there are pending events (current > last triggered)
            pending_events = current_count - last_triggered_count
            if pending_events <= 0:
                continue

            # Parse timestamps to datetime for robust comparison
            # All timestamps are stored in ISO 8601 UTC format
            try:
                last_event_at = datetime.fromisoformat(last_event_at_str.replace("Z", "+00:00"))
                # Ensure timezone-aware comparison
                if last_event_at.tzinfo is None:
                    last_event_at = last_event_at.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                # Skip if timestamp is invalid
                self._log(
                    f"Invalid last_event_at timestamp for alert {alert_uuid}",
                    level="warning",
                    alert_uuid=alert_uuid,
                    last_event_at=last_event_at_str,
                )
                continue

            # Check if last event is within the time window
            if last_event_at < cutoff:
                continue

            # Check if we haven't triggered since the last event (or never triggered at all)
            if last_triggered_at_str is not None:
                try:
                    last_triggered_at = datetime.fromisoformat(last_triggered_at_str.replace("Z", "+00:00"))
                    if last_triggered_at.tzinfo is None:
                        last_triggered_at = last_triggered_at.replace(tzinfo=timezone.utc)
                    # Skip if already triggered after last event
                    if last_triggered_at >= last_event_at:
                        continue
                except (ValueError, AttributeError):
                    # If timestamp is invalid, treat as not triggered
                    pass

            pending_alerts.append(state)
            self._log(
                f"Alert {state.get('alert_short_id')} pending for time check",
                level="debug",
                alert_uuid=alert_uuid,
                pending_events=pending_events,
                last_event_at=last_event_at_str,
            )

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
