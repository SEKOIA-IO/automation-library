import time
import uuid
from datetime import datetime, timedelta, timezone
from posixpath import join as urljoin
from threading import Lock, Thread, Event
from typing import Any, Optional

import orjson
import requests
import urllib3
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger
from .helpers.state_manager import AlertStateManager
from .metrics import EVENTS_FORWARDED, EVENTS_FILTERED, THRESHOLD_CHECKS, STATE_SIZE


class SecurityAlertsTrigger(_SEKOIANotificationBaseTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "created"), ("alert", "updated"), ("alert-comment", "created")]

    def handle_event(self, message):
        """Handle alert messages.

        Only a few event are considered (`alert:created`,
        `alert:updated`, `alert-comment:created`). If a valid evnet is
        handled, then enrich event from `sicalertapi` to retrieve its
        status, its short id, etc. Finally, send message to the
        Symphony workflow.

        """
        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore alert “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            return

        # Is the notification in a format we can understand?
        alert_uuid: str = alert_attrs.get("uuid", "")
        if not alert_uuid:
            return

        if not self._filter_notifications(message):
            return

        try:
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from Alert API")
            return

        if rule_filter := self.configuration.get("rule_filter"):
            if alert["rule"]["name"] != rule_filter and alert["rule"]["uuid"] != rule_filter:
                return

        if rule_names_filter := self.configuration.get("rule_names_filter"):
            if alert["rule"]["name"] not in rule_names_filter:
                return

        work_dir = self._data_path.joinpath("sekoiaio_securityalerts").joinpath(str(uuid.uuid4()))
        alert_path = work_dir.joinpath("alert.json")
        work_dir.mkdir(parents=True, exist_ok=True)

        with alert_path.open("w") as fp:
            fp.write(orjson.dumps(alert).decode("utf-8"))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(alert_path.relative_to(work_dir))

        alert_short_id = alert.get("short_id")
        event = {
            "file_path": file_path,
            "event_type": event_type,
            "alert_uuid": alert_uuid,
            "short_id": alert_short_id,
            "status": {
                "name": alert.get("status", {}).get("name"),
                "uuid": alert.get("status", {}).get("uuid"),
            },
            "created_at": alert.get("created_at"),
            "urgency": alert.get("urgency", {}).get("current_value"),
            "entity": alert.get("entity", {}),
            "alert_type": alert.get("alert_type", {}),
            "rule": {"name": alert.get("rule", {}).get("name"), "uuid": alert.get("rule", {}).get("uuid")},
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
        }

        self.send_event(
            event_name=f"Sekoia.io Alert: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    def _filter_notifications(self, message) -> bool:
        return True

    @retry(
        reraise=True,
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(10),
    )
    def _retrieve_alert_from_alertapi(self, alert_uuid):
        api_url = urljoin(self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}")
        api_url = api_url.replace("/api/api", "/api")  # In case base_url ends with /api

        api_key = self.module.configuration["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()}

        response = requests.get(
            api_url,
            headers=headers,
            params={
                "stix": False,
                "comments": False,
                "countermeasures": False,
                "history": False,
            },
        )

        if not response.ok:
            try:
                content = response.json()
            except Exception:
                content = response.text
            self.log(
                "Error while fetching alert from Alert API",
                level="error",
                status_code=response.status_code,
                content=content,
            )

        # raise an exception if the http request failed
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exp:
            self.log("Failed to parse JSON response from Alert API", level="error", content=response.text)
            raise exp


class AlertCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "created")]


class AlertUpdatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "updated")]


class AlertStatusChangedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert", "updated")]

    def _filter_notifications(self, message) -> bool:
        if message.get("attributes", {}).get("updated", {}).get("status"):
            return True
        return False


class AlertCommentCreatedTrigger(SecurityAlertsTrigger):
    # List of alert types we can handle.
    HANDLED_EVENT_SUB_TYPES = [("alert-comment", "created")]

    def handle_event(self, message):
        """Handle alert messages.

        Only a few event are considered (`alert:created`,
        `alert:updated`, `alert-comment:created`). If a valid evnet is
        handled, then enrich event from `sicalertapi` to retrieve its
        status, its short id, etc. Finally, send message to the
        Symphony workflow.

        """
        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Ignore alert “sub event” types that we can’t (yet) handle.
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            return

        # Is the notification in a format we can understand?
        alert_uuid: str = alert_attrs.get("alert_uuid", "")
        if not alert_uuid:
            return

        comment_uuid: str = alert_attrs.get("uuid", "")
        if not comment_uuid:
            return

        if not self._filter_notifications(message):
            return

        try:
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
            comment = self._retrieve_comment_from_alertapi(alert_uuid, comment_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from Alert API")
            return

        if rule_filter := self.configuration.get("rule_filter"):
            if alert["rule"]["name"] != rule_filter and alert["rule"]["uuid"] != rule_filter:
                return

        if rule_names_filter := self.configuration.get("rule_names_filter"):
            if alert["rule"]["name"] not in rule_names_filter:
                return

        work_dir = self._data_path.joinpath("sekoiaio_securityalerts").joinpath(str(uuid.uuid4()))
        alert_path = work_dir.joinpath("alert.json")
        work_dir.mkdir(parents=True, exist_ok=True)

        with alert_path.open("w") as fp:
            fp.write(orjson.dumps(alert).decode("utf-8"))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(alert_path.relative_to(work_dir))

        alert_short_id = alert.get("short_id")
        event = {
            "comment": {
                "uuid": comment.get("uuid"),
                "content": comment.get("content"),
                "author": comment.get("created_by"),
                "date": comment.get("date"),
            },
            "file_path": file_path,
            "event_type": event_type,
            "alert_uuid": alert_uuid,
            "short_id": alert_short_id,
            "status": {
                "name": alert.get("status", {}).get("name"),
                "uuid": alert.get("status", {}).get("uuid"),
            },
            "created_at": alert.get("created_at"),
            "urgency": alert.get("urgency", {}).get("current_value"),
            "entity": alert.get("entity", {}),
            "alert_type": alert.get("alert_type", {}),
            "rule": {"name": alert.get("rule", {}).get("name"), "uuid": alert.get("rule", {}).get("uuid")},
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
        }

        self.send_event(
            event_name=f"Sekoia.io Alert: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    @retry(
        reraise=True,
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(10),
    )
    def _retrieve_comment_from_alertapi(self, alert_uuid: str, comment_uuid: str):
        api_url = urljoin(
            self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}/comments/{comment_uuid}"
        )

        api_url = api_url.replace("/api/api", "/api")  # In case base_url ends with /api

        api_key = self.module.configuration["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent()}

        response = requests.get(api_url, headers=headers)

        if not response.ok:
            try:
                content = response.json()
            except Exception:
                content = response.text
            self.log(
                "Error while fetching alert comment from Alert API",
                level="error",
                status_code=response.status_code,
                content=content,
            )

        # raise an exception if the http request failed
        response.raise_for_status()
        try:
            return response.json()
        except Exception as exp:
            self.log("Failed to parse JSON response from Alert Comment API", level="error", content=response.text)
            raise exp


# ==============================================================================
# Alert Events Threshold Trigger
# ==============================================================================


class AlertEventsThresholdConfiguration(BaseModel):
    """
    Configuration for the Alert Events Threshold Trigger.
    """

    model_config = ConfigDict(extra="ignore")

    # User-configurable parameters
    rule_filter: Optional[str] = Field(
        None,
        description="Filter by rule name or UUID (single rule only)",
    )

    rule_names_filter: list[str] = Field(
        default_factory=list,
        description="Filter by multiple rule names",
    )

    event_count_threshold: int = Field(
        default=100,
        ge=1,
        description="Minimum number of new events to trigger (volume-based)",
    )

    time_window_hours: int = Field(
        default=1,
        ge=1,
        le=168,
        description="Time window in hours for time-based triggering (max 7 days)",
    )

    enable_volume_threshold: bool = Field(
        default=True,
        description="Enable volume-based threshold (>= N events)",
    )

    enable_time_threshold: bool = Field(
        default=True,
        description="Enable time-based threshold (activity in last N hours)",
    )

    state_cleanup_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Remove state entries for alerts older than N days",
    )

    fetch_events: bool = Field(
        default=False,
        description="Whether to fetch and include events in the trigger output",
    )

    fetch_all_events: bool = Field(
        default=False,
        description="If True, fetch all events from the alert. If False, fetch only new events since last trigger",
    )

    max_events_per_fetch: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of events to fetch per trigger execution",
    )

    @model_validator(mode="after")
    def validate_at_least_one_threshold(self):
        """Ensure at least one threshold is enabled."""
        if not self.enable_volume_threshold and not self.enable_time_threshold:
            raise ValueError("At least one threshold must be enabled")
        return self

    @model_validator(mode="after")
    def validate_configuration_consistency(self):
        """Validate configuration parameter relationships."""
        # Both filters set is confusing
        if self.rule_filter and self.rule_names_filter:
            raise ValueError("Use either rule_filter OR rule_names_filter, not both")

        # Cleanup should be longer than time window
        if self.state_cleanup_days * 24 < self.time_window_hours:
            raise ValueError("state_cleanup_days must be longer than time_window_hours")

        return self


class AlertEventsThresholdTrigger(SecurityAlertsTrigger):
    """
    Trigger that monitors alert updates and triggers playbooks only when
    event accumulation thresholds are met.

    Supports dual threshold logic:
    - Volume-based: Trigger if >= N new events added
    - Time-based: Trigger if >= 1 event added in last N hours

    This trigger extends SecurityAlertsTrigger to reuse common alert handling logic
    like API retrieval and rule filtering.

    Concurrency handling:
    - In-memory locks prevent race conditions within a single pod
    - S3 state persistence ensures state survives pod restarts
    - Multi-pod deployments: In rare cases with high-frequency updates to the same
      alert across multiple pods, duplicate triggers may occur. This is acceptable
      as S3 writes are atomic and the impact is minimal (1-2 extra triggers vs 20+
      without locks).
    """

    # Handle alert creation and updates
    HANDLED_EVENT_SUB_TYPES = [("alert", "created"), ("alert", "updated")]

    # Interval for periodic time threshold check (in seconds)
    # Check every 5 minutes to balance responsiveness vs resource usage
    TIME_THRESHOLD_CHECK_INTERVAL_SECONDS = 300

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager: Optional[AlertStateManager] = None
        self._last_cleanup: Optional[datetime] = None
        self._initialized = False
        self._validated_config: Optional[AlertEventsThresholdConfiguration] = None
        self._http_session: Optional[requests.Session] = None
        self._events_api_path: Optional[str] = None
        self._alert_locks: dict[str, Lock] = {}
        self._locks_lock = Lock()  # Lock to protect access to _alert_locks dictionary
        self._max_locks = 1024  # Maximum number of locks to keep in memory
        # Periodic time threshold check thread
        self._time_threshold_thread: Optional[Thread] = None
        self._time_threshold_stop_event = Event()

    def _get_alert_lock(self, alert_uuid: str) -> Lock:
        """
        Get or create a lock for a specific alert to prevent concurrent processing.

        Implements bounded cache with max 1024 locks. When threshold is exceeded,
        prunes unlocked entries to prevent unbounded memory growth.
        """
        with self._locks_lock:
            # Clean up unlocked entries if we've hit the max
            if len(self._alert_locks) >= self._max_locks:
                # Remove locks that are not currently acquired
                unlocked = [uuid for uuid, lock in self._alert_locks.items() if not lock.locked()]
                for uuid in unlocked[: len(unlocked) // 2]:  # Remove half of unlocked locks
                    del self._alert_locks[uuid]

                if len(self._alert_locks) >= self._max_locks:
                    self.log(
                        message=f"Alert locks cache at capacity ({len(self._alert_locks)} locks)",
                        level="warning",
                        max_locks=self._max_locks,
                    )

            if alert_uuid not in self._alert_locks:
                self._alert_locks[alert_uuid] = Lock()
            return self._alert_locks[alert_uuid]

    def _start_time_threshold_thread(self):
        """Start the periodic time threshold check thread."""
        if self._time_threshold_thread is not None and self._time_threshold_thread.is_alive():
            self.log(message="Time threshold thread already running", level="debug")
            return

        self._time_threshold_stop_event.clear()
        self._time_threshold_thread = Thread(
            target=self._time_threshold_check_loop,
            name="TimeThresholdChecker",
            daemon=True,
        )
        self._time_threshold_thread.start()
        self.log(
            message="Started time threshold check thread",
            level="info",
            interval_seconds=self.TIME_THRESHOLD_CHECK_INTERVAL_SECONDS,
        )

    def _stop_time_threshold_thread(self):
        """Stop the periodic time threshold check thread."""
        if self._time_threshold_thread is None:
            return

        self._time_threshold_stop_event.set()
        self._time_threshold_thread.join(timeout=10)
        if self._time_threshold_thread.is_alive():
            self.log(message="Time threshold thread did not stop cleanly", level="warning")
            # Keep reference to thread so we don't create duplicates
            # Thread is daemon so it will be killed when main process exits
        else:
            self.log(message="Time threshold thread stopped", level="debug")
            self._time_threshold_thread = None

    def _time_threshold_check_loop(self):
        """
        Periodic loop that checks time thresholds for pending alerts.

        This runs in a separate thread and checks every TIME_THRESHOLD_CHECK_INTERVAL_SECONDS.
        """
        self.log(message="Time threshold check loop started", level="debug")

        while not self._time_threshold_stop_event.is_set():
            try:
                self._check_pending_time_thresholds()
            except Exception as exp:
                self.log_exception(exp, message="Error in time threshold check loop")

            # Wait for interval or stop event
            self._time_threshold_stop_event.wait(timeout=self.TIME_THRESHOLD_CHECK_INTERVAL_SECONDS)

        self.log(message="Time threshold check loop stopped", level="debug")

    def _check_pending_time_thresholds(self):
        """
        Check all pending alerts for time threshold triggers.

        This is called periodically by the time threshold thread.
        """
        if self.state_manager is None:
            return

        config = self.validated_config
        if not config.enable_time_threshold:
            return

        time_window_hours = config.time_window_hours

        self.log(
            message="Checking pending time thresholds",
            level="debug",
            time_window_hours=time_window_hours,
        )

        # Reload state to get latest data from S3
        try:
            self.state_manager.reload_state()
        except Exception as exp:
            self.log_exception(exp, message="Failed to reload state for time threshold check")
            return

        pending_alerts = self.state_manager.get_alerts_pending_time_check(time_window_hours)

        if not pending_alerts:
            self.log(message="No pending alerts for time threshold check", level="debug")
            return

        self.log(
            message=f"Found {len(pending_alerts)} alerts pending time threshold check",
            level="debug",
            pending_count=len(pending_alerts),
        )

        for alert_state in pending_alerts:
            try:
                self._trigger_time_threshold_for_alert(alert_state)
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to trigger time threshold for alert",
                    alert_uuid=alert_state.get("alert_uuid"),
                )

    def _trigger_time_threshold_for_alert(self, alert_state: dict[str, Any]):
        """
        Trigger the playbook for an alert that meets the time threshold.

        Args:
            alert_state: Alert state from state manager
        """
        alert_uuid = alert_state.get("alert_uuid")
        alert_short_id = alert_state.get("alert_short_id")

        # Type guards for required fields
        if not isinstance(alert_uuid, str) or not isinstance(alert_short_id, str):
            self.log(
                message="Invalid alert state: missing alert_uuid or alert_short_id",
                level="error",
                alert_uuid=alert_uuid,
                alert_short_id=alert_short_id,
            )
            return

        if self.state_manager is None:
            self.log(message="State manager not initialized", level="error")
            return

        current_count = alert_state.get("current_event_count", 0)
        last_triggered_count = alert_state.get("last_triggered_event_count", 0)
        new_events = current_count - last_triggered_count

        self.log(
            message=f"Triggering time threshold for alert {alert_short_id}",
            level="info",
            alert_uuid=alert_uuid,
            new_events=new_events,
            current_count=current_count,
        )

        # Get alert info from cache
        alert = alert_state.get("alert_info")
        if alert is None:
            self.log(
                message=f"No cached alert info for {alert_short_id}, skipping time threshold trigger",
                level="warning",
                alert_uuid=alert_uuid,
            )
            return

        # Use lock to prevent race condition with notification handler
        alert_lock = self._get_alert_lock(alert_uuid)
        with alert_lock:
            # Re-check state after acquiring lock (may have been updated)
            current_state = self.state_manager.get_alert_state(alert_uuid)
            if current_state is None:
                return

            # Re-calculate new events with fresh state
            current_count = current_state.get("current_event_count", 0)
            last_triggered_count = current_state.get("last_triggered_event_count", 0)
            new_events = current_count - last_triggered_count

            if new_events <= 0:
                self.log(
                    message=f"No new events for alert {alert_short_id} after lock (already triggered)",
                    level="debug",
                    alert_uuid=alert_uuid,
                )
                return

            context = {
                "reason": "time_threshold",
                "new_events": new_events,
                "previous_count": last_triggered_count,
                "current_count": current_count,
                "time_window_hours": self.validated_config.time_window_hours,
            }

            # Update state
            try:
                self.state_manager.update_alert_state(
                    alert_uuid=alert_uuid,
                    alert_short_id=alert_short_id,
                    rule_uuid=alert.get("rule", {}).get("uuid", ""),
                    rule_name=alert.get("rule", {}).get("name", ""),
                    event_count=current_count,
                    previous_version=current_state.get("version"),
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to update state for time threshold trigger")
                # Continue despite error

            # Send event to playbook
            try:
                self._send_threshold_event(
                    alert=alert,
                    event_type="alert",
                    context=context,
                    events=None,  # No event fetch for periodic triggers
                    previous_state=current_state,
                )

                EVENTS_FORWARDED.labels(trigger_type="time_threshold").inc()

                self.log(
                    message=f"Time threshold triggered for alert {alert_short_id}",
                    level="info",
                    alert_uuid=alert_uuid,
                    new_events=new_events,
                )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to send time threshold event",
                    alert_uuid=alert_uuid,
                )

    @property
    def validated_config(self) -> AlertEventsThresholdConfiguration:
        """
        Get validated configuration using Pydantic model.
        Lazily validates and caches the configuration.
        """
        if self._validated_config is None:
            self.log(message="Validating trigger configuration", level="debug")
            try:
                self._validated_config = AlertEventsThresholdConfiguration(**self.configuration)
                self.log(
                    message="Configuration validated successfully",
                    level="debug",
                    config=str(self._validated_config.model_dump()),
                )
            except Exception as exp:
                self.log_exception(exp, message="Configuration validation failed", raw_config=str(self.configuration))
                raise
        return self._validated_config

    def _ensure_initialized(self):
        """Lazy initialization of state manager and HTTP session."""
        if not self._initialized:
            self.log(message="Initializing AlertEventsThresholdTrigger", level="debug")
            state_path = self._data_path / "alert_thresholds_state.json"
            self.log(message=f"State file path: {state_path}", level="debug")

            try:
                self.state_manager = AlertStateManager(state_path, logger=self.log)

                # Initialize HTTP session for events API
                # Normalize base_url: remove trailing slashes and ensure it doesn't end with /api
                base_url = self.module.configuration["base_url"].rstrip("/")
                if base_url.endswith("/api"):
                    base_url = base_url[:-4]
                self._events_api_path = f"{base_url}/api/v1/sic/conf/events"

                self._http_session = requests.Session()
                self._http_session.headers.update(
                    {
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self.module.configuration['api_key']}",
                        "User-Agent": user_agent(),
                    }
                )

                self._initialized = True

                # Start periodic time threshold check thread if enabled
                config = self.validated_config
                if config.enable_time_threshold:
                    self._start_time_threshold_thread()

                self.log(
                    message="AlertEventsThresholdTrigger initialized successfully",
                    level="info",
                    state_path=str(state_path),
                    events_api_path=self._events_api_path,
                    time_threshold_enabled=config.enable_time_threshold,
                    time_window_hours=config.time_window_hours,
                )
            except Exception as exp:
                self.log_exception(
                    exp, message="Failed to initialize AlertEventsThresholdTrigger", state_path=str(state_path)
                )
                raise

    def stop(self, *args, **kwargs):
        """Stop the trigger and clean up resources."""
        self.log(message="Stopping AlertEventsThresholdTrigger", level="info")

        # Stop the time threshold thread
        self._stop_time_threshold_thread()

        # Close HTTP session
        if self._http_session is not None:
            self._http_session.close()
            self._http_session = None

        # Call parent stop
        super().stop(*args, **kwargs)

        self.log(message="AlertEventsThresholdTrigger stopped", level="info")

    def handle_event(self, message):
        """
        Handle alert update messages with threshold evaluation.

        This method overrides the parent class to add threshold logic before
        triggering the playbook.
        """
        self.log(
            message="Received event message",
            level="debug",
            message_type=message.get("type"),
            message_action=message.get("action"),
        )

        # Ensure state manager is initialized
        try:
            self._ensure_initialized()
        except Exception as exp:
            self.log_exception(exp, message="Failed to initialize in handle_event, aborting")
            return

        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        # Only handle alert updates
        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            self.log(
                message="Event type not handled, skipping",
                level="debug",
                event_type=event_type,
                event_action=event_action,
                handled_types=str(self.HANDLED_EVENT_SUB_TYPES),
            )
            return

        # Extract alert UUID
        alert_uuid: str = alert_attrs.get("uuid", "")
        if not alert_uuid:
            self.log(message="Notification missing alert UUID", level="warning", message_attributes=str(alert_attrs))
            return

        # Extract event count from notification (similar field contains total event count)
        # For alert:updated -> similar is in attributes.updated.similar
        # For alert:created -> similar is in attributes.similar
        updated_fields = alert_attrs.get("updated", {})
        event_count_from_notification: Optional[int] = updated_fields.get("similar")
        if event_count_from_notification is None:
            # Fallback to direct similar field (for alert:created notifications)
            event_count_from_notification = alert_attrs.get("similar")

        # Use a lock to prevent concurrent processing of the same alert
        alert_lock = self._get_alert_lock(alert_uuid)
        with alert_lock:
            self._handle_event_locked(alert_uuid, event_type, message, event_count_from_notification)

    def _handle_event_locked(
        self, alert_uuid: str, event_type: str, message: dict, event_count_from_notification: Optional[int] = None
    ):
        """
        Handle alert update with lock acquired.
        This method contains the actual logic that was previously in handle_event.

        Args:
            alert_uuid: UUID of the alert
            event_type: Type of the event (e.g., "alert")
            message: Full notification message
            event_count_from_notification: Total event count from Kafka notification (similar field)
        """
        self.log(message="Processing alert event", level="debug", alert_uuid=alert_uuid)

        event_action = message.get("action", "")
        alert_attrs = message.get("attributes", {})

        # Try to get alert info without API call
        alert = self._get_alert_info_optimized(alert_uuid, event_action, alert_attrs)
        if alert is None:
            self.log(
                message="Could not retrieve alert info, skipping",
                level="warning",
                alert_uuid=alert_uuid,
            )
            return

        # Update state with current event count (for time threshold periodic check)
        if self.state_manager is not None and event_count_from_notification is not None:
            try:
                self.state_manager.update_alert_info(
                    alert_uuid=alert_uuid,
                    alert_info=alert,
                    event_count=event_count_from_notification,
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to update alert info in state", alert_uuid=alert_uuid)
                # Continue despite error

        # Apply rule filtering
        if not self._should_process_alert(alert):
            EVENTS_FILTERED.labels(reason="rule_filter").inc()
            self.log(
                message=f"Alert {alert.get('short_id')} filtered out by rule filter",
                level="debug",
                alert_uuid=alert_uuid,
                rule_name=alert.get("rule", {}).get("name"),
                rule_uuid=alert.get("rule", {}).get("uuid"),
            )
            return

        self.log(message=f"Alert {alert.get('short_id')} passed rule filter", level="debug", alert_uuid=alert_uuid)

        # Load previous state for this alert
        try:
            if self.state_manager is None:
                self.log(message="State manager not initialized", level="error", alert_uuid=alert_uuid)
                return

            previous_state = self.state_manager.get_alert_state(alert_uuid)
            self.log(
                message=f"Loaded previous state for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                has_previous_state=previous_state is not None,
                previous_count=previous_state.get("last_triggered_event_count") if previous_state else 0,
            )
        except Exception as exp:
            self.log_exception(
                exp, message="Failed to load previous state, continuing without it", alert_uuid=alert_uuid
            )
            previous_state = None

        # Evaluate thresholds
        try:
            self.log(
                message=f"Evaluating thresholds for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                event_count_from_notification=event_count_from_notification,
            )
            should_trigger, context = self._evaluate_thresholds(alert, previous_state, event_count_from_notification)
            self.log(
                message=f"Threshold evaluation completed for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                should_trigger=should_trigger,
                trigger_context=str(context),
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to evaluate thresholds",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id"),
            )
            return

        if not should_trigger:
            EVENTS_FILTERED.labels(reason="threshold_not_met").inc()
            self.log(
                message=f"Alert {alert.get('short_id')} does not meet thresholds: {context.get('reason', 'unknown')}",
                level="debug",
                alert_uuid=alert_uuid,
                new_events=context.get("new_events"),
                current_count=context.get("current_count"),
                previous_count=context.get("previous_count"),
            )
            return

        # Update state before triggering
        try:
            if self.state_manager is None:
                self.log(
                    message="State manager not initialized, cannot update state", level="error", alert_uuid=alert_uuid
                )
                return

            self.log(message=f"Updating state for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
            self.state_manager.update_alert_state(
                alert_uuid=alert_uuid,
                alert_short_id=str(alert.get("short_id", "")),
                rule_uuid=str(alert.get("rule", {}).get("uuid", "")),
                rule_name=str(alert.get("rule", {}).get("name", "")),
                event_count=context.get("current_count", 0),  # Use current_count from threshold evaluation
                previous_version=previous_state.get("version") if previous_state else None,
            )
            self.log(
                message=f"State updated successfully for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to update alert state",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id"),
            )
            # Continue despite state update failure

        # Periodic cleanup of old states
        try:
            self._cleanup_old_states()
        except Exception as exp:
            self.log_exception(exp, message="Failed to cleanup old states, continuing")
            # Continue despite cleanup failure

        # Fetch events if configured
        events = None
        config = self.validated_config
        if config.fetch_events:
            try:
                self.log(
                    message=f"Fetching events for alert {alert.get('short_id')}",
                    level="debug",
                    alert_uuid=alert_uuid,
                    fetch_all=config.fetch_all_events,
                    max_events=config.max_events_per_fetch,
                )
                events = self._fetch_alert_events(
                    alert=alert,
                    fetch_all=config.fetch_all_events,
                    previous_state=previous_state,
                    max_events=config.max_events_per_fetch,
                )
                if events is None:
                    self.log(
                        message=f"Failed to fetch events for alert {alert.get('short_id')}, continuing without events",
                        level="warning",
                        alert_uuid=alert_uuid,
                    )
                else:
                    self.log(
                        message=f"Fetched {len(events)} events for alert {alert.get('short_id')}",
                        level="info",
                        alert_uuid=alert_uuid,
                        events_count=len(events),
                    )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to fetch events, continuing without events",
                    alert_uuid=alert_uuid,
                    alert_short_id=alert.get("short_id"),
                )
                # Continue without events

        # Reuse parent's method for creating event payload
        try:
            self.log(
                message=f"Sending threshold event for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
            )
            self._send_threshold_event(
                alert=alert,
                event_type=event_type,
                context=context,
                events=events,
                previous_state=previous_state,
            )
            self.log(
                message=f"Threshold event sent successfully for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to send threshold event",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id"),
            )
            return

        # Increment metrics for each trigger type separately to avoid high cardinality
        trigger_reason = context["reason"]
        if "first_occurrence" in trigger_reason:
            EVENTS_FORWARDED.labels(trigger_type="first_occurrence").inc()
        if "volume_threshold" in trigger_reason:
            EVENTS_FORWARDED.labels(trigger_type="volume_threshold").inc()
        if "time_threshold" in trigger_reason:
            EVENTS_FORWARDED.labels(trigger_type="time_threshold").inc()

        self.log(
            message=f"Triggered for alert {alert.get('short_id')}: {context['new_events']} new events ({context['reason']})",
            level="info",
            alert_uuid=alert_uuid,
            alert_short_id=alert.get("short_id"),
            new_events=context["new_events"],
            trigger_reason=context["reason"],
            current_count=context["current_count"],
            previous_count=context["previous_count"],
        )

    def _should_process_alert(self, alert: dict[str, Any]) -> bool:
        """
        Check if alert should be processed based on rule filters.

        This reuses the parent class logic for consistency.

        Args:
            alert: Alert data dictionary

        Returns:
            True if alert matches filters (or no filters configured)
        """
        config = self.validated_config
        rule_filter = config.rule_filter
        rule_names_filter = config.rule_names_filter

        # No filters: accept all
        if not rule_filter and not rule_names_filter:
            self.log(message="No rule filters configured, accepting all alerts", level="debug")
            return True

        rule_name = alert.get("rule", {}).get("name")
        rule_uuid = alert.get("rule", {}).get("uuid")

        # Single rule filter (note: config validation ensures rule_filter and rule_names_filter are mutually exclusive)
        if rule_filter:
            matches = rule_name == rule_filter or rule_uuid == rule_filter
            self.log(
                message=f"Single rule filter check: {matches}",
                level="debug",
                configured_filter=rule_filter,
                alert_rule_name=rule_name,
                alert_rule_uuid=rule_uuid,
            )
            return matches

        # Multiple rule names filter (only reached if rule_filter is None)
        matches = rule_name in rule_names_filter
        self.log(
            message=f"Multiple rule names filter check: {matches}",
            level="debug",
            configured_filters=str(rule_names_filter),
            alert_rule_name=rule_name,
        )
        return matches

    def _get_alert_info_optimized(
        self, alert_uuid: str, event_action: str, alert_attrs: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Get alert info optimized to avoid API calls when possible.

        Strategy:
        1. If alert:created -> extract info from notification, no API call
        2. If alert:updated and state has cached info -> use cache, no API call
        3. If alert:updated and no cache -> API call, then cache

        Args:
            alert_uuid: UUID of the alert
            event_action: Action from notification ("created" or "updated")
            alert_attrs: Attributes from notification

        Returns:
            Alert info dictionary or None if could not retrieve
        """
        # Case 1: alert:created - extract from notification
        if event_action == "created":
            alert = self._extract_alert_from_created_notification(alert_attrs)
            self.log(
                message="Using alert info from created notification",
                level="debug",
                alert_uuid=alert_uuid,
                short_id=alert.get("short_id"),
            )
            return alert

        # Case 2 & 3: alert:updated - check cache first
        if self.state_manager is not None:
            cached_alert = self.state_manager.get_alert_info(alert_uuid)
            if cached_alert is not None:
                self.log(
                    message="Using cached alert info from state",
                    level="debug",
                    alert_uuid=alert_uuid,
                    short_id=cached_alert.get("short_id"),
                )
                return cached_alert

        # Case 3: No cache, need API call
        try:
            self.log(message=f"Fetching alert {alert_uuid} from API (no cache)", level="debug")
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
            self.log(
                message=f"Successfully retrieved alert {alert.get('short_id')} from API",
                level="debug",
                alert_uuid=alert_uuid,
                short_id=alert.get("short_id"),
            )
            return alert
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from Alert API", alert_uuid=alert_uuid)
            return None

    def _extract_alert_from_created_notification(self, alert_attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Extract alert info from alert:created notification attributes.

        The alert:created notification contains all the alert fields we need.

        Args:
            alert_attrs: Attributes from the notification

        Returns:
            Alert info dictionary in the same format as API response
        """
        return {
            "uuid": alert_attrs.get("uuid"),
            "short_id": alert_attrs.get("short_id"),
            "status": {
                "name": alert_attrs.get("status_name"),
                "uuid": alert_attrs.get("status_uuid"),
            },
            "urgency": {
                "current_value": alert_attrs.get("urgency_current_value"),
            },
            "alert_type": {
                "category": alert_attrs.get("alert_type_category"),
                "value": alert_attrs.get("alert_type_value"),
            },
            "rule": {
                "uuid": alert_attrs.get("rule_uuid"),
                "name": alert_attrs.get("rule_name"),
            },
            "entity": {
                "uuid": alert_attrs.get("entity_uuid"),
                "name": alert_attrs.get("entity_name"),
            },
            "assets": [{"uuid": uuid} for uuid in alert_attrs.get("assets_uuids", [])],
            # These fields are not in alert:created notification, will be None
            "created_at": None,
            "first_seen_at": None,
            "last_seen_at": None,
        }

    def _send_threshold_event(
        self,
        alert: dict[str, Any],
        event_type: str,
        context: dict[str, Any],
        events: Optional[list[dict[str, Any]]] = None,
        previous_state: Optional[dict[str, Any]] = None,
    ):
        """
        Send event to playbook with threshold context.

        This extends the parent's event creation with threshold-specific information.

        Args:
            alert: Alert data dictionary
            event_type: Type of the event
            context: Threshold evaluation context
            events: Optional list of events to include
            previous_state: Previous state for this alert
        """
        import uuid as uuid_lib

        alert_short_id = alert.get("short_id")
        alert_uuid = alert.get("uuid")

        self.log(
            message=f"Creating threshold event for alert {alert_short_id}",
            level="debug",
            alert_uuid=alert_uuid,
            event_type=event_type,
            include_events=events is not None,
            events_count=len(events) if events else 0,
        )

        # Create work directory for alert data
        try:
            work_dir = self._data_path.joinpath("sekoiaio_alert_threshold").joinpath(str(uuid_lib.uuid4()))
            alert_path = work_dir.joinpath("alert.json")
            work_dir.mkdir(parents=True, exist_ok=True)
            self.log(message=f"Created work directory: {work_dir}", level="debug")
        except Exception as exp:
            self.log_exception(
                exp, message="Failed to create work directory", alert_uuid=alert_uuid, alert_short_id=alert_short_id
            )
            raise

        try:
            with alert_path.open("w") as fp:
                fp.write(orjson.dumps(alert).decode("utf-8"))
            self.log(message=f"Wrote alert data to {alert_path}", level="debug")
        except Exception as exp:
            self.log_exception(
                exp, message="Failed to write alert data to file", alert_path=str(alert_path), alert_uuid=alert_uuid
            )
            raise

        # Save events if provided
        events_file_path = None
        if events is not None:
            try:
                events_path = work_dir.joinpath("events.json")
                with events_path.open("w") as fp:
                    fp.write(orjson.dumps(events).decode("utf-8"))
                events_file_path = str(events_path.relative_to(work_dir))
                self.log(
                    message=f"Wrote {len(events)} events to {events_path}",
                    level="debug",
                    events_count=len(events),
                )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to write events to file",
                    events_path=str(events_path) if "events_path" in locals() else None,
                    alert_uuid=alert_uuid,
                )
                # Continue without events file

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(alert_path.relative_to(work_dir))

        # Build event payload (similar to parent but with threshold context)
        event = {
            "file_path": file_path,
            "event_type": event_type,
            "alert_uuid": alert["uuid"],
            "short_id": alert_short_id,
            "status": {
                "name": alert.get("status", {}).get("name"),
                "uuid": alert.get("status", {}).get("uuid"),
            },
            "created_at": alert.get("created_at"),
            "urgency": alert.get("urgency", {}).get("current_value"),
            "entity": alert.get("entity", {}),
            "alert_type": alert.get("alert_type", {}),
            "rule": {"name": alert.get("rule", {}).get("name"), "uuid": alert.get("rule", {}).get("uuid")},
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
            "events_count": context.get("current_count", 0),  # Use current_count from threshold evaluation
            # Add threshold-specific context
            "trigger_context": {
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "trigger_type": "alert_events_threshold",
                **context,
            },
        }

        # Add events file path if events were fetched
        if events_file_path:
            event["events_file_path"] = events_file_path
            event["fetched_events_count"] = len(events) if events else 0

        self.log(
            message=f"Built event payload for alert {alert_short_id}",
            level="debug",
            event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
            directory=directory,
        )

        try:
            self.send_event(
                event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
                event=event,
                directory=directory,
                remove_directory=True,
            )
            self.log(
                message=f"Event sent successfully for alert {alert_short_id}", level="info", alert_uuid=alert_uuid
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to send event to playbook",
                alert_uuid=alert_uuid,
                alert_short_id=alert_short_id,
                event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
            )
            raise

    def _evaluate_thresholds(
        self,
        alert: dict[str, Any],
        previous_state: Optional[dict[str, Any]],
        event_count_from_notification: Optional[int] = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Evaluate whether alert meets triggering thresholds.

        Args:
            alert: Current alert data
            previous_state: Previous state for this alert (if any)
            event_count_from_notification: Total event count from Kafka notification (similar field)

        Returns:
            Tuple of (should_trigger, trigger_context)
        """
        alert_uuid = alert["uuid"]

        # Use event count from Kafka notification if available, otherwise fall back to API
        if event_count_from_notification is not None:
            current_event_count = event_count_from_notification
            self.log(
                message="Using event count from Kafka notification",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=current_event_count,
            )
        else:
            # Fall back to API call if notification doesn't contain event count
            api_event_count = self._get_total_event_count(alert)
            if api_event_count is None:
                self.log(
                    message="Failed to get event count from API, using 0",
                    level="warning",
                    alert_uuid=alert_uuid,
                )
                current_event_count = 0
            else:
                current_event_count = api_event_count
                self.log(
                    message="Using event count from API (fallback)",
                    level="debug",
                    alert_uuid=alert_uuid,
                    event_count=current_event_count,
                )

        self.log(
            message="Starting threshold evaluation",
            level="debug",
            alert_uuid=alert_uuid,
            current_event_count=current_event_count,
            has_previous_state=previous_state is not None,
        )

        # First time seeing this alert: trigger immediately
        if previous_state is None:
            context = {
                "reason": "first_occurrence",
                "new_events": current_event_count,
                "previous_count": 0,
                "current_count": current_event_count,
            }
            THRESHOLD_CHECKS.labels(triggered="true").inc()
            self.log(
                message="First occurrence of alert, triggering immediately",
                level="debug",
                alert_uuid=alert_uuid,
                current_event_count=current_event_count,
            )
            return True, context

        previous_count = previous_state.get("last_triggered_event_count", 0)
        new_events = current_event_count - previous_count

        self.log(
            message="Comparing event counts",
            level="debug",
            alert_uuid=alert_uuid,
            previous_count=previous_count,
            current_count=current_event_count,
            new_events=new_events,
        )

        # No new events: skip
        if new_events <= 0:
            THRESHOLD_CHECKS.labels(triggered="false").inc()
            self.log(
                message="No new events since last trigger, skipping",
                level="debug",
                alert_uuid=alert_uuid,
                previous_count=previous_count,
                current_count=current_event_count,
            )
            return False, {"reason": "no_new_events"}

        trigger_reasons = []
        config = self.validated_config

        # Volume-based threshold
        enable_volume = config.enable_volume_threshold
        event_count_threshold = config.event_count_threshold

        self.log(
            message="Checking volume-based threshold",
            level="debug",
            alert_uuid=alert_uuid,
            enable_volume=enable_volume,
            event_count_threshold=event_count_threshold,
            new_events=new_events,
        )

        if enable_volume and new_events >= event_count_threshold:
            trigger_reasons.append("volume_threshold")
            self.log(
                message=f"Volume threshold met: {new_events} >= {event_count_threshold}",
                level="debug",
                alert_uuid=alert_uuid,
            )

        # Time-based threshold
        enable_time = config.enable_time_threshold
        time_window_hours = config.time_window_hours

        self.log(
            message="Checking time-based threshold",
            level="debug",
            alert_uuid=alert_uuid,
            enable_time=enable_time,
            time_window_hours=time_window_hours,
        )

        if enable_time:
            try:
                events_in_window = self._count_events_in_time_window(
                    alert_uuid,
                    time_window_hours,
                )
                if events_in_window is None:
                    # API call failed, skip time threshold check (fail open)
                    self.log(
                        message="Time threshold check skipped due to API error (fail open)",
                        level="warning",
                        alert_uuid=alert_uuid,
                        time_window_hours=time_window_hours,
                    )
                else:
                    self.log(
                        message=f"Events in time window: {events_in_window}",
                        level="debug",
                        alert_uuid=alert_uuid,
                        time_window_hours=time_window_hours,
                        events_in_window=events_in_window,
                    )
                    if events_in_window > 0:
                        trigger_reasons.append("time_threshold")
                        self.log(
                            message=f"Time threshold met: {events_in_window} events in last {time_window_hours}h",
                            level="debug",
                            alert_uuid=alert_uuid,
                        )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to check time-based threshold, skipping",
                    alert_uuid=alert_uuid,
                    time_window_hours=time_window_hours,
                )

        should_trigger = len(trigger_reasons) > 0

        context = {
            "reason": ", ".join(trigger_reasons) if trigger_reasons else "no_threshold_met",
            "new_events": new_events,
            "previous_count": previous_count,
            "current_count": current_event_count,
            "time_window_hours": time_window_hours,
        }

        THRESHOLD_CHECKS.labels(triggered="true" if should_trigger else "false").inc()

        self.log(
            message=f"Threshold evaluation result: should_trigger={should_trigger}",
            level="debug",
            alert_uuid=alert_uuid,
            should_trigger=should_trigger,
            trigger_reasons=str(trigger_reasons),
            new_events=new_events,
        )

        return should_trigger, context

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _trigger_event_search_job(
        self, alert_short_id: str, earliest_time: str, latest_time: str, limit: int
    ) -> Optional[str]:
        """
        Trigger an event search job for a specific alert.

        Args:
            alert_short_id: Short ID of the alert
            earliest_time: Start time for event search (ISO 8601)
            latest_time: End time for event search (ISO 8601)
            limit: Maximum number of events to retrieve

        Returns:
            UUID of the search job, or None if failed
        """
        query = f'alert_short_ids:"{alert_short_id}"'

        data = {
            "term": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "visible": False,
            "max_last_events": limit,
        }

        self.log(
            message=f"Triggering event search job for alert {alert_short_id}",
            level="debug",
            alert_short_id=alert_short_id,
            query=query,
            earliest_time=earliest_time,
            latest_time=latest_time,
            limit=limit,
        )

        try:
            if self._http_session is None:
                self.log(message="HTTP session not initialized", level="error")
                return None

            response = self._http_session.post(
                f"{self._events_api_path}/search/jobs",
                json=data,
                timeout=20,
            )
            response.raise_for_status()

            job_uuid = response.json()["uuid"]
            self.log(
                message=f"Event search job triggered successfully",
                level="debug",
                alert_short_id=alert_short_id,
                job_uuid=job_uuid,
            )
            return job_uuid

        except Exception as e:
            self.log_exception(e, message="Failed to trigger event search job", alert_short_id=alert_short_id)
            return None

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _wait_for_search_job(self, job_uuid: str, timeout: int = 300) -> bool:
        """
        Wait for a search job to complete.

        Args:
            job_uuid: UUID of the search job
            timeout: Maximum time to wait in seconds

        Returns:
            True if job completed successfully, False otherwise
        """
        if self._http_session is None:
            self.log(message="HTTP session not initialized", level="error")
            return False

        start_time = time.time()

        self.log(message=f"Waiting for search job {job_uuid} to complete", level="debug", job_uuid=job_uuid)

        try:
            # Wait for job to start (status != 0)
            while True:
                response = self._http_session.get(
                    f"{self._events_api_path}/search/jobs/{job_uuid}",
                    timeout=20,
                )
                response.raise_for_status()
                status = response.json()["status"]

                if status != 0:
                    break

                if time.time() - start_time > timeout:
                    self.log(
                        message=f"Search job {job_uuid} timed out waiting to start", level="error", job_uuid=job_uuid
                    )
                    return False

                time.sleep(1)

            # Wait for job to complete (status != 1)
            while True:
                response = self._http_session.get(
                    f"{self._events_api_path}/search/jobs/{job_uuid}",
                    timeout=20,
                )
                response.raise_for_status()
                status = response.json()["status"]

                if status != 1:
                    break

                if time.time() - start_time > timeout:
                    self.log(
                        message=f"Search job {job_uuid} timed out waiting to complete",
                        level="error",
                        job_uuid=job_uuid,
                    )
                    return False

                time.sleep(1)

            self.log(message=f"Search job {job_uuid} completed", level="debug", job_uuid=job_uuid)
            return True

        except Exception as e:
            self.log_exception(e, message=f"Failed to wait for search job {job_uuid}", job_uuid=job_uuid)
            return False

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _get_search_job_results(self, job_uuid: str, limit: int) -> Optional[list[dict[str, Any]]]:
        """
        Retrieve results from a completed search job.

        Args:
            job_uuid: UUID of the search job
            limit: Maximum number of results to retrieve per page

        Returns:
            List of events, or None if failed
        """
        if self._http_session is None:
            self.log(message="HTTP session not initialized", level="error")
            return None

        self.log(
            message=f"Retrieving results for search job {job_uuid}",
            level="debug",
            job_uuid=job_uuid,
            limit=limit,
        )

        results: list[dict[str, Any]] = []
        offset = 0
        total = None
        page_size = limit

        try:
            while total is None or offset < total:
                response = self._http_session.get(
                    f"{self._events_api_path}/search/jobs/{job_uuid}/events",
                    params={"limit": page_size, "offset": offset},
                    timeout=20,
                )
                response.raise_for_status()

                data = response.json()
                items = data.get("items", [])

                if not items:
                    num_results = len(results)
                    if num_results < data.get("total", 0):
                        self.log(
                            "Number of fetched results doesn't match total",
                            level="warning",
                            num_results=num_results,
                            total=data.get("total", 0),
                            job_uuid=job_uuid,
                        )
                    break

                results.extend(items)
                if total is None:
                    total = data.get("total", 0)
                offset += page_size

            self.log(
                message=f"Retrieved {len(results)} events from search job",
                level="debug",
                job_uuid=job_uuid,
                total_events=len(results),
            )

            return results

        except Exception as e:
            self.log_exception(e, message=f"Failed to get search job results", job_uuid=job_uuid)
            return None

    def _fetch_alert_events(
        self,
        alert: dict[str, Any],
        fetch_all: bool,
        previous_state: Optional[dict[str, Any]],
        max_events: int,
    ) -> Optional[list[dict[str, Any]]]:
        """
        Fetch events from an alert using the search job API.

        Args:
            alert: Alert data dictionary
            fetch_all: If True, fetch all events. If False, fetch only new events
            previous_state: Previous state for this alert (to get last trigger time)
            max_events: Maximum number of events to fetch

        Returns:
            List of events, or None if API call failed
        """
        alert_short_id = alert.get("short_id")
        alert_uuid = alert.get("uuid")
        first_seen_at = alert.get("first_seen_at")
        last_seen_at = alert.get("last_seen_at")

        # Validate required fields
        if not alert_short_id or not first_seen_at or not last_seen_at:
            self.log(
                message="Alert missing required fields for event fetching",
                level="error",
                alert_uuid=alert_uuid,
                has_short_id=bool(alert_short_id),
                has_first_seen_at=bool(first_seen_at),
                has_last_seen_at=bool(last_seen_at),
            )
            return None

        # Determine time range based on fetch_all flag
        if fetch_all:
            earliest_time = first_seen_at
            self.log(
                message=f"Fetching all events for alert {alert_short_id}",
                level="debug",
                alert_uuid=alert_uuid,
                earliest_time=earliest_time,
                latest_time=last_seen_at,
            )
        else:
            # Fetch only new events since last trigger
            if previous_state and previous_state.get("last_triggered_at"):
                earliest_time = previous_state["last_triggered_at"]
            else:
                # First run, use first_seen_at
                earliest_time = first_seen_at

            self.log(
                message=f"Fetching new events for alert {alert_short_id}",
                level="debug",
                alert_uuid=alert_uuid,
                earliest_time=earliest_time,
                latest_time=last_seen_at,
            )

        # Step 1: Trigger the search job
        job_uuid = self._trigger_event_search_job(alert_short_id, earliest_time, last_seen_at, max_events)
        if not job_uuid:
            self.log(message="Failed to trigger search job", level="error", alert_uuid=alert_uuid)
            return None

        # Step 2: Wait for the job to complete
        if not self._wait_for_search_job(job_uuid):
            self.log(message="Search job did not complete", level="error", alert_uuid=alert_uuid, job_uuid=job_uuid)
            return None

        # Step 3: Get the results (use 100 as page size like in get_events.py)
        events = self._get_search_job_results(job_uuid, 100)
        if events is None:
            self.log(
                message="Failed to get search job results", level="error", alert_uuid=alert_uuid, job_uuid=job_uuid
            )
            return None

        self.log(
            message=f"Fetched {len(events)} events for alert {alert_short_id}",
            level="info",
            alert_uuid=alert_uuid,
            alert_short_id=alert_short_id,
            events_count=len(events),
            fetch_all=fetch_all,
        )

        return events

    def _get_total_event_count(self, alert: dict[str, Any]) -> Optional[int]:
        """
        Get total count of events for an alert using the search job API.

        This method triggers a search job with size=0 to get only the total count
        without fetching all events, which is much more efficient.

        Args:
            alert: Alert data dictionary (must contain short_id, first_seen_at, last_seen_at)

        Returns:
            Total number of events, or None if API call failed
        """
        alert_uuid = alert.get("uuid")
        alert_short_id = alert.get("short_id")
        first_seen_at = alert.get("first_seen_at")
        last_seen_at = alert.get("last_seen_at")

        self.log(
            message=f"Getting total event count for alert {alert_uuid}",
            level="debug",
            alert_uuid=alert_uuid,
        )

        if not alert_short_id or not first_seen_at or not last_seen_at:
            self.log(
                message="Alert missing required fields for event counting",
                level="error",
                alert_uuid=alert_uuid,
                has_short_id=bool(alert_short_id),
                has_first_seen_at=bool(first_seen_at),
                has_last_seen_at=bool(last_seen_at),
            )
            return None

        # Step 1: Trigger the search job with max_last_events=1 to minimize data transfer
        job_uuid = self._trigger_event_search_job(alert_short_id, first_seen_at, last_seen_at, limit=1)
        if not job_uuid:
            self.log(message="Failed to trigger search job for event counting", level="error", alert_uuid=alert_uuid)
            return None

        # Step 2: Wait for the job to complete
        if not self._wait_for_search_job(job_uuid):
            self.log(
                message="Search job did not complete for event counting",
                level="error",
                alert_uuid=alert_uuid,
                job_uuid=job_uuid,
            )
            return None

        # Step 3: Get only the first page to extract the total count
        try:
            if self._http_session is None:
                self.log(message="HTTP session not initialized", level="error")
                return None

            response = self._http_session.get(
                f"{self._events_api_path}/search/jobs/{job_uuid}/events",
                params={"limit": 1, "offset": 0},  # Only fetch 1 item to get the total
                timeout=20,
            )
            response.raise_for_status()

            data = response.json()
            event_count = data.get("total", 0)

            self.log(
                message=f"Successfully got total event count",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=event_count,
            )

            return event_count

        except Exception as e:
            self.log_exception(e, message=f"Failed to get event count from search job", alert_uuid=alert_uuid)
            return None

    def _count_events_in_time_window(
        self,
        alert_uuid: str,
        hours: int,
    ) -> Optional[int]:
        """
        Count events added to alert within the last N hours.

        Args:
            alert_uuid: UUID of the alert
            hours: Time window in hours

        Returns:
            Number of events in the time window, or None if API call failed
            (None indicates unchecked state, allowing fail-open behavior)
        """
        earliest_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        self.log(
            message=f"Counting events in time window for alert {alert_uuid}",
            level="debug",
            alert_uuid=alert_uuid,
            hours=hours,
            earliest_time=earliest_time.isoformat(),
        )

        api_url = urljoin(self.module.configuration["base_url"], "api/v2/events/search")
        api_url = api_url.replace("/api/api", "/api")

        api_key = self.module.configuration["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent(),
        }

        payload = {
            "filter": {
                "alert_uuid": alert_uuid,
                "created_at": {
                    "gte": earliest_time.isoformat(),
                },
            },
            "size": 0,  # We only need the count
        }

        self.log(message=f"Calling events API: {api_url}", level="debug", alert_uuid=alert_uuid, payload=str(payload))

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)

            self.log(
                message=f"Events API response received",
                level="debug",
                alert_uuid=alert_uuid,
                status_code=response.status_code,
            )

            if not response.ok:
                try:
                    error_content = response.json()
                except Exception:
                    error_content = response.text
                self.log(
                    message="Events API returned error",
                    level="error",
                    alert_uuid=alert_uuid,
                    status_code=response.status_code,
                    error_content=str(error_content),
                )

            response.raise_for_status()
            data = response.json()
            event_count = data.get("total", 0)

            self.log(
                message=f"Successfully counted events in time window",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=event_count,
                hours=hours,
            )

            return event_count
        except requests.exceptions.Timeout as e:
            self.log(
                message=f"Timeout counting events for alert {alert_uuid}",
                level="error",
                alert_uuid=alert_uuid,
                timeout=30,
                error=str(e),
            )
            return None  # Return None to indicate unchecked (fail open: skip this check)
        except requests.exceptions.RequestException as e:
            self.log(
                message=f"Request error counting events for alert {alert_uuid}",
                level="error",
                alert_uuid=alert_uuid,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None  # Return None to indicate unchecked (fail open: skip this check)
        except Exception as e:
            self.log_exception(e, message=f"Failed to count events for alert {alert_uuid}", alert_uuid=alert_uuid)
            return None  # Return None to indicate unchecked (fail open: skip this check)

    def _cleanup_old_states(self):
        """
        Periodically clean up state entries for old alerts (once per day).
        """
        now = datetime.now(timezone.utc)

        # Only run once per day
        if self._last_cleanup and (now - self._last_cleanup).total_seconds() < 86400:
            seconds_since_last = (now - self._last_cleanup).total_seconds()
            self.log(
                message=f"Cleanup not needed yet (last run {seconds_since_last:.0f}s ago)",
                level="debug",
                seconds_since_last_cleanup=seconds_since_last,
            )
            return

        self.log(message="Starting state cleanup", level="debug")

        config = self.validated_config
        state_cleanup_days = config.state_cleanup_days
        cutoff_date = now - timedelta(days=state_cleanup_days)

        self.log(
            message=f"Cleaning up states older than {state_cleanup_days} days",
            level="debug",
            state_cleanup_days=state_cleanup_days,
            cutoff_date=cutoff_date.isoformat(),
        )

        try:
            if not self.state_manager:
                self.log(message="State manager not initialized, skipping cleanup", level="warning")
                return

            removed = self.state_manager.cleanup_old_states(cutoff_date)

            # Update state size metric
            state_size = len(self.state_manager._state["alerts"])
            STATE_SIZE.set(state_size)

            if removed > 0:
                self.log(
                    message=f"State cleanup: removed {removed} entries older than {state_cleanup_days} days",
                    level="info",
                    removed_count=removed,
                    state_cleanup_days=state_cleanup_days,
                    remaining_states=state_size,
                )
            else:
                self.log(
                    message="State cleanup: no old entries to remove",
                    level="debug",
                    state_cleanup_days=state_cleanup_days,
                    remaining_states=state_size,
                )

            self._last_cleanup = now
        except Exception as exp:
            self.log_exception(exp, message="Failed to cleanup old states", state_cleanup_days=state_cleanup_days)
            # Don't update _last_cleanup if cleanup failed, will retry next time
