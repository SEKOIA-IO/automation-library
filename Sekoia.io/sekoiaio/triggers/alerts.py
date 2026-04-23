import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from posixpath import join as urljoin
from threading import Event, Lock, Thread
from typing import Any

import orjson
import requests
import urllib3
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger
from .helpers.state_manager import AlertStateManager
from .metrics import EVENTS_FILTERED, EVENTS_FORWARDED, STATE_SIZE, THRESHOLD_CHECKS


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
            "custom_status": {
                "name": alert.get("custom_status", {}).get("label"),
                "level": alert.get("custom_status", {}).get("level"),
                "stage": alert.get("custom_status", {}).get("stage"),
                "uuid": alert.get("custom_status_uuid"),
            },
            "verdict": {
                "name": alert.get("verdict", {}).get("label"),
                "level": alert.get("verdict", {}).get("level"),
                "stage": alert.get("verdict", {}).get("stage"),
                "uuid": alert.get("verdict_uuid"),
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
                "custom_status": True,
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
    rule_filter: str | None = Field(
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.state_manager: AlertStateManager | None = None
        self._last_cleanup: datetime | None = None
        self._initialized: bool = False
        self._validated_config: AlertEventsThresholdConfiguration | None = None
        self._http_session: requests.Session | None = None
        self._events_api_path: str | None = None
        self._alert_locks: OrderedDict[str, Lock] = OrderedDict()
        self._locks_lock: Lock = Lock()
        self._max_alert_locks: int = 10_000
        self._time_threshold_thread: Thread | None = None
        self._time_threshold_stop_event: Event = Event()

    def _get_alert_lock(self, alert_uuid: str) -> Lock:
        """Get or create a per-alert lock, with LRU eviction to bound memory growth.

        Alerts that are filtered out (by rule_filter) or malformed never reach
        persisted state, so their locks cannot be freed by the state cleanup path.
        An LRU bound ensures the dict stays below _max_alert_locks entries.

        Eviction skips locks that are currently acquired to avoid race conditions
        where two threads could process the same alert concurrently.
        """
        with self._locks_lock:
            if alert_uuid in self._alert_locks:
                self._alert_locks.move_to_end(alert_uuid)
                return self._alert_locks[alert_uuid]
            if len(self._alert_locks) >= self._max_alert_locks:
                self._evict_oldest_unlocked()
            lock = Lock()
            self._alert_locks[alert_uuid] = lock
            return lock

    def _evict_oldest_unlocked(self) -> None:
        """Evict the oldest unlocked entry from the alert locks dict.

        Must be called while holding self._locks_lock.
        """
        for uuid in list(self._alert_locks.keys()):
            if not self._alert_locks[uuid].locked():
                del self._alert_locks[uuid]
                return

    def _start_time_threshold_thread(self) -> None:
        """Start the periodic time threshold check thread."""
        if self._time_threshold_thread is not None and self._time_threshold_thread.is_alive():
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

    def _stop_time_threshold_thread(self) -> None:
        """Stop the periodic time threshold check thread."""
        if self._time_threshold_thread is None:
            return

        self._time_threshold_stop_event.set()
        self._time_threshold_thread.join(timeout=10)
        if self._time_threshold_thread.is_alive():
            self.log(message="Time threshold thread did not stop cleanly", level="warning")
        else:
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

    def _check_pending_time_thresholds(self) -> None:
        """Check all pending alerts for time threshold triggers."""
        if self.state_manager is None:
            return

        config = self.validated_config

        try:
            self.state_manager.reload_state()
        except Exception as exp:
            self.log_exception(exp, message="Failed to reload state for time threshold check")
            return

        # Run cleanup unconditionally (self-throttled to once/day) so that state
        # and locks are pruned even when time_threshold is disabled (volume-only
        # configs) or when there are no pending alerts.
        self._cleanup_old_states()

        if not config.enable_time_threshold:
            return

        pending_alerts = self.state_manager.get_alerts_pending_time_check(config.time_window_hours)
        if not pending_alerts:
            return

        for alert_state in pending_alerts:
            try:
                self._trigger_time_threshold_for_alert(alert_state)
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to trigger time threshold for alert",
                    alert_uuid=alert_state.get("alert_uuid"),
                )

    def _trigger_time_threshold_for_alert(self, alert_state: dict[str, Any]) -> None:
        """Trigger the playbook for an alert that meets the time threshold."""
        alert_uuid = alert_state.get("alert_uuid")
        alert_short_id = alert_state.get("alert_short_id")

        if not isinstance(alert_uuid, str) or not isinstance(alert_short_id, str):
            self.log(message="Invalid alert state: missing uuid or short_id", level="error")
            return

        if self.state_manager is None:
            return

        alert = alert_state.get("alert_info")
        if alert is None:
            self.log(
                message=f"No cached alert info for {alert_short_id}, skipping time threshold",
                level="warning",
                alert_uuid=alert_uuid,
            )
            return

        alert_lock = self._get_alert_lock(alert_uuid)
        with alert_lock:
            # Re-check after acquiring lock (state may have been updated by notification handler)
            current_state = self.state_manager.get_alert_state(alert_uuid)
            if current_state is None:
                return

            # Use freshest alert_info from current state (may have been updated by notification)
            alert = current_state.get("alert_info") or alert

            current_count = current_state.get("current_event_count", 0)
            last_triggered_count = current_state.get("last_triggered_event_count", 0)
            new_events = current_count - last_triggered_count

            if new_events <= 0:
                return

            context = {
                "reason": "time_threshold",
                "new_events": new_events,
                "previous_count": last_triggered_count,
                "current_count": current_count,
                "time_window_hours": self.validated_config.time_window_hours,
            }

            try:
                self.state_manager.update_alert_state(
                    alert_uuid=alert_uuid,
                    alert_short_id=alert_short_id,
                    rule_uuid=alert.get("rule", {}).get("uuid", ""),
                    rule_name=alert.get("rule", {}).get("name", ""),
                    event_count=current_count,
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to update state for time threshold")

            try:
                self._send_threshold_event(alert=alert, event_type="alert", context=context)
                EVENTS_FORWARDED.labels(trigger_type="time_threshold").inc()
                self.log(
                    message=f"Time threshold triggered for alert {alert_short_id}",
                    level="info",
                    alert_uuid=alert_uuid,
                    new_events=new_events,
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to send time threshold event", alert_uuid=alert_uuid)

    @property
    def validated_config(self) -> AlertEventsThresholdConfiguration:
        """Get validated configuration, lazily initialized and cached."""
        if self._validated_config is None:
            self._validated_config = AlertEventsThresholdConfiguration(**self.configuration)
        return self._validated_config

    def _ensure_initialized(self) -> None:
        """Lazy initialization of state manager, HTTP session, and background thread."""
        if self._initialized:
            return

        state_path = self._data_path / "alert_thresholds_state.json"
        self.state_manager = AlertStateManager(state_path, logger=self.log)

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

        if self.validated_config.enable_time_threshold:
            self._start_time_threshold_thread()

        self.log(message="AlertEventsThresholdTrigger initialized", level="info")

    def stop(self, *args, **kwargs) -> None:
        """Stop the trigger and clean up resources."""
        self._stop_time_threshold_thread()
        if self._http_session is not None:
            self._http_session.close()
            self._http_session = None
        super().stop(*args, **kwargs)

    def handle_event(self, message: dict[str, Any]) -> None:
        """Handle alert update messages with threshold evaluation."""
        try:
            self._ensure_initialized()
        except Exception as exp:
            self.log_exception(exp, message="Failed to initialize, aborting")
            return

        # Run cleanup from handle_event so volume-only configurations (where the
        # background time-threshold thread is not started) still prune old state
        # and stale locks. The method self-throttles to once per day.
        self._cleanup_old_states()

        alert_attrs = message.get("attributes", {})
        event_type: str = message.get("type", "")
        event_action: str = message.get("action", "")

        if (event_type, event_action) not in self.HANDLED_EVENT_SUB_TYPES:
            return

        alert_uuid: str = alert_attrs.get("uuid", "")
        if not alert_uuid:
            self.log(message="Notification missing alert UUID", level="warning")
            return

        # Extract event count from notification (similar field)
        event_count_from_notification = self._extract_event_count(alert_attrs)

        alert_lock = self._get_alert_lock(alert_uuid)
        with alert_lock:
            self._handle_event_locked(alert_uuid, event_type, message, event_count_from_notification)

    def _extract_event_count(self, alert_attrs: dict[str, Any]) -> int | None:
        """Extract and validate event count from notification attributes."""
        raw_count = alert_attrs.get("updated", {}).get("similar")
        if raw_count is None:
            raw_count = alert_attrs.get("similar")
        if raw_count is None:
            return None
        try:
            return int(raw_count)
        except (TypeError, ValueError):
            self.log(message=f"Invalid event count in notification: {raw_count!r}", level="warning")
            return None

    def _handle_event_locked(
        self,
        alert_uuid: str,
        event_type: str,
        message: dict[str, Any],
        event_count_from_notification: int | None = None,
    ) -> None:
        """Process an alert notification under lock. Core threshold logic."""
        event_action = message.get("action", "")
        alert_attrs = message.get("attributes", {})

        # Get alert info (from notification, cache, or API)
        alert = self._get_alert_info_optimized(alert_uuid, event_action, alert_attrs)
        if alert is None:
            self.log(message="Could not retrieve alert info, skipping", level="warning", alert_uuid=alert_uuid)
            return

        if not self._should_process_alert(alert):
            EVENTS_FILTERED.labels(reason="rule_filter").inc()
            return

        # Reload state from S3 to get latest version (prevents race conditions)
        try:
            if self.state_manager is None:
                return
            self.state_manager.reload_state()
            previous_state = self.state_manager.get_alert_state(alert_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to load previous state", alert_uuid=alert_uuid)
            previous_state = None

        # Evaluate thresholds
        try:
            should_trigger, context = self._evaluate_thresholds(alert, previous_state, event_count_from_notification)
        except Exception as exp:
            self.log_exception(exp, message="Failed to evaluate thresholds", alert_uuid=alert_uuid)
            return

        if not should_trigger:
            EVENTS_FILTERED.labels(reason="threshold_not_met").inc()
            # Store alert info for the background time threshold checker regardless of
            # whether the count came from the notification or the 0 fallback — the
            # background thread needs the cached alert_info to fire later.
            if self.state_manager is not None:
                event_count = event_count_from_notification if event_count_from_notification is not None else 0
                try:
                    self.state_manager.update_alert_info(
                        alert_uuid=alert_uuid,
                        alert_info=alert,
                        event_count=event_count,
                    )
                except Exception as exp:
                    self.log_exception(exp, message="Failed to update alert info", alert_uuid=alert_uuid)
            return

        # Update state before triggering
        if self.state_manager is not None:
            try:
                self.state_manager.update_alert_state(
                    alert_uuid=alert_uuid,
                    alert_short_id=str(alert.get("short_id", "")),
                    rule_uuid=str(alert.get("rule", {}).get("uuid", "")),
                    rule_name=str(alert.get("rule", {}).get("name", "")),
                    event_count=context.get("current_count", 0),
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to update alert state", alert_uuid=alert_uuid)

        # Fetch events if configured
        events: list[dict[str, Any]] | None = None
        config = self.validated_config
        if config.fetch_events:
            try:
                events = self._fetch_alert_events(
                    alert=alert,
                    fetch_all=config.fetch_all_events,
                    previous_state=previous_state,
                    max_events=config.max_events_per_fetch,
                )
            except Exception as exp:
                self.log_exception(exp, message="Failed to fetch events", alert_uuid=alert_uuid)

        # Send event to playbook
        try:
            self._send_threshold_event(alert=alert, event_type=event_type, context=context, events=events)
        except Exception as exp:
            self.log_exception(exp, message="Failed to send threshold event", alert_uuid=alert_uuid)
            return

        # Update metrics
        trigger_reason = context["reason"]
        for reason_key in ("first_occurrence", "volume_threshold", "time_threshold"):
            if reason_key in trigger_reason:
                EVENTS_FORWARDED.labels(trigger_type=reason_key).inc()

        if self.state_manager is not None:
            STATE_SIZE.set(len(self.state_manager.get_all_alerts()))

        self.log(
            message=f"Triggered for alert {alert.get('short_id')}: {context['new_events']} new events ({trigger_reason})",
            level="info",
            alert_uuid=alert_uuid,
        )

    def _should_process_alert(self, alert: dict[str, Any]) -> bool:
        """Check if alert matches configured rule filters."""
        config = self.validated_config

        if not config.rule_filter and not config.rule_names_filter:
            return True

        rule_name = alert.get("rule", {}).get("name")
        rule_uuid = alert.get("rule", {}).get("uuid")

        if config.rule_filter:
            return rule_name == config.rule_filter or rule_uuid == config.rule_filter

        return rule_name in config.rule_names_filter

    def _get_alert_info_optimized(
        self, alert_uuid: str, event_action: str, alert_attrs: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Get alert info, avoiding API calls when possible.

        Strategy:
        1. alert:created → extract from notification
        2. alert:updated with cached state → use cache
        3. alert:updated without cache → API call
        """
        if event_action == "created":
            return self._extract_alert_from_created_notification(alert_attrs)

        if self.state_manager is not None:
            cached_alert = self.state_manager.get_alert_info(alert_uuid)
            if cached_alert is not None:
                return cached_alert

        try:
            return self._retrieve_alert_from_alertapi(alert_uuid)
        except Exception as exp:
            self.log_exception(exp, message="Failed to fetch alert from API", alert_uuid=alert_uuid)
            return None

    def _extract_alert_from_created_notification(self, alert_attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Extract alert info from alert:created notification attributes.

        The alert:created notification contains all the alert fields we need.
        For temporal fields not present in the notification, we use the current
        timestamp as a reasonable default (the alert was just created).

        Args:
            alert_attrs: Attributes from the notification

        Returns:
            Alert info dictionary in the same format as API response
        """
        # Use current time as default for temporal fields not in notification
        # This is reasonable since alert:created means the alert was just created
        now_iso = datetime.now(timezone.utc).isoformat()

        return {
            "uuid": alert_attrs.get("uuid"),
            "short_id": alert_attrs.get("short_id"),
            "status": {
                "name": alert_attrs.get("status_name"),
                "uuid": alert_attrs.get("status_uuid"),
            },
            # custom_status and verdict are typically absent on newly created alerts;
            # default to empty dicts so _send_threshold_event can access them safely
            # without producing KeyError or requiring None-guards downstream.
            "custom_status": {},
            "verdict": {},
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
            # Temporal fields: use notification values if present, else current time
            # (alert:created means the alert was just created, so current time is reasonable)
            "created_at": alert_attrs.get("created_at", now_iso),
            "first_seen_at": alert_attrs.get("first_seen_at", now_iso),
            "last_seen_at": alert_attrs.get("last_seen_at", now_iso),
        }

    def _send_threshold_event(
        self,
        alert: dict[str, Any],
        event_type: str,
        context: dict[str, Any],
        events: list[dict[str, Any]] | None = None,
    ) -> None:
        """Send event to playbook with threshold context."""
        alert_short_id = alert.get("short_id")

        # Write alert data to temp directory
        work_dir = self._data_path.joinpath("sekoiaio_alert_threshold").joinpath(str(uuid.uuid4()))
        alert_path = work_dir.joinpath("alert.json")
        work_dir.mkdir(parents=True, exist_ok=True)

        with alert_path.open("w") as fp:
            fp.write(orjson.dumps(alert).decode("utf-8"))

        # Write events if provided
        events_file_path: str | None = None
        if events is not None:
            events_path = work_dir.joinpath("events.json")
            with events_path.open("w") as fp:
                fp.write(orjson.dumps(events).decode("utf-8"))
            events_file_path = str(events_path.relative_to(work_dir))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(alert_path.relative_to(work_dir))

        # Build event payload — consistent with SecurityAlertsTrigger + threshold context
        event: dict[str, Any] = {
            "file_path": file_path,
            "event_type": event_type,
            "alert_uuid": alert.get("uuid"),
            "short_id": alert_short_id,
            "status": {
                "name": alert.get("status", {}).get("name"),
                "uuid": alert.get("status", {}).get("uuid"),
            },
            "custom_status": {
                "name": alert.get("custom_status", {}).get("label"),
                "level": alert.get("custom_status", {}).get("level"),
                "stage": alert.get("custom_status", {}).get("stage"),
                "uuid": alert.get("custom_status_uuid"),
            },
            "verdict": {
                "name": alert.get("verdict", {}).get("label"),
                "level": alert.get("verdict", {}).get("level"),
                "stage": alert.get("verdict", {}).get("stage"),
                "uuid": alert.get("verdict_uuid"),
            },
            "created_at": alert.get("created_at"),
            "urgency": alert.get("urgency", {}).get("current_value"),
            "entity": alert.get("entity", {}),
            "alert_type": alert.get("alert_type", {}),
            "rule": {
                "name": alert.get("rule", {}).get("name"),
                "uuid": alert.get("rule", {}).get("uuid"),
            },
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
            "events_count": context.get("current_count", 0),
            "trigger_context": {
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "trigger_type": "alert_events_threshold",
                **context,
            },
        }

        if events_file_path:
            event["events_file_path"] = events_file_path
            event["fetched_events_count"] = len(events) if events else 0

        self.send_event(
            event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
            event=event,
            directory=directory,
            remove_directory=True,
        )

    def _evaluate_thresholds(
        self,
        alert: dict[str, Any],
        previous_state: dict[str, Any] | None,
        event_count_from_notification: int | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Evaluate whether alert meets triggering thresholds.

        Returns:
            Tuple of (should_trigger, trigger_context)
        """
        # Resolve current event count from notification metadata.
        # We intentionally do NOT fall back to a search job API call here because:
        # 1. The search job is async and expensive (POST + polling + GET), blocking the
        #    greenlet under the per-alert lock for several seconds.
        # 2. The main case where event_count_from_notification is None is alert:created
        #    with no "similar" field — meaning the alert has 0-1 events, which will never
        #    meet the volume threshold anyway.
        # 3. The time threshold background thread will catch these alerts later, so no
        #    data is lost — just deferred.
        if event_count_from_notification is not None:
            current_event_count = event_count_from_notification
        else:
            # Default to 0: the alert will be picked up by the time threshold checker
            # once events accumulate and the time window elapses.
            current_event_count = 0

        config = self.validated_config

        # Compute delta
        if previous_state is None:
            previous_count = 0
            new_events = current_event_count
            is_first_occurrence = True
        else:
            previous_count = previous_state.get("last_triggered_event_count", 0)
            new_events = current_event_count - previous_count
            is_first_occurrence = False

        if new_events <= 0:
            THRESHOLD_CHECKS.labels(triggered="false").inc()
            return False, {"reason": "no_new_events"}

        trigger_reasons: list[str] = []

        # Volume-based threshold
        if config.enable_volume_threshold and new_events >= config.event_count_threshold:
            trigger_reasons.append("volume_threshold")
            if is_first_occurrence:
                trigger_reasons.append("first_occurrence")

        # Time-based threshold is handled by the periodic background thread
        # (_time_threshold_check_loop), not inline on each notification.
        # This creates a cooldown of time_window_hours between triggers.

        should_trigger = len(trigger_reasons) > 0

        context = {
            "reason": ", ".join(trigger_reasons) if trigger_reasons else "no_threshold_met",
            "new_events": new_events,
            "previous_count": previous_count,
            "current_count": current_event_count,
            "time_window_hours": config.time_window_hours,
        }

        THRESHOLD_CHECKS.labels(triggered=str(should_trigger).lower()).inc()
        return should_trigger, context

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _trigger_event_search_job(self, alert_short_id: str, earliest_time: str, latest_time: str, limit: int) -> str:
        """
        Trigger an event search job for a specific alert.

        Args:
            alert_short_id: Short ID of the alert
            earliest_time: Start time for event search (ISO 8601)
            latest_time: End time for event search (ISO 8601)
            limit: Maximum number of events to retrieve

        Returns:
            UUID of the search job

        Raises:
            requests.HTTPError: If the API call fails after retries
        """
        if self._http_session is None:
            raise RuntimeError("HTTP session not initialized")

        query = f'alert_short_ids:"{alert_short_id}"'
        data = {
            "term": query,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "visible": False,
            "max_last_events": limit,
        }

        response = self._http_session.post(
            f"{self._events_api_path}/search/jobs",
            json=data,
            timeout=20,
        )
        response.raise_for_status()

        return response.json()["uuid"]

    def _wait_for_search_job(self, job_uuid: str, timeout: int = 300, poll_interval: int = 2) -> bool:
        """
        Wait for a search job to complete.

        Args:
            job_uuid: UUID of the search job
            timeout: Maximum time to wait in seconds
            poll_interval: Seconds between status checks

        Returns:
            True if job completed successfully, False otherwise

        Raises:
            requests.HTTPError: If a non-transient status check fails (4xx)
        """
        if self._http_session is None:
            raise RuntimeError("HTTP session not initialized")

        start_time = time.time()

        # Poll until job is done (status 0=pending, 1=running, 2+=done).
        # Transient errors (timeouts, 5xx) are logged and retried on the next
        # poll cycle to stay consistent with the other API helpers.
        while True:
            try:
                response = self._http_session.get(
                    f"{self._events_api_path}/search/jobs/{job_uuid}",
                    timeout=20,
                )
                response.raise_for_status()
                status = response.json()["status"]
            except (requests.exceptions.Timeout, urllib3.exceptions.TimeoutError) as exc:
                self.log(
                    message=f"Transient timeout polling search job {job_uuid}, retrying",
                    level="warning",
                    job_uuid=job_uuid,
                    error=str(exc),
                )
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None and exc.response.status_code < 500:
                    raise  # 4xx: permanent failure, propagate immediately
                self.log(
                    message=f"Transient HTTP error polling search job {job_uuid}, retrying",
                    level="warning",
                    job_uuid=job_uuid,
                    error=str(exc),
                )
            else:
                if status >= 2:
                    return True

            if time.time() - start_time > timeout:
                self.log(
                    message=f"Search job {job_uuid} timed out after {timeout}s",
                    level="error",
                    job_uuid=job_uuid,
                )
                return False

            time.sleep(poll_interval)

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def _get_search_job_events_page(self, job_uuid: str, limit: int, offset: int) -> dict[str, Any]:
        """Fetch a single page of search job results (retriable)."""
        if self._http_session is None:
            raise RuntimeError("HTTP session not initialized")

        response = self._http_session.get(
            f"{self._events_api_path}/search/jobs/{job_uuid}/events",
            params={"limit": limit, "offset": offset},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def _get_search_job_results(self, job_uuid: str, page_size: int = 100) -> list[dict[str, Any]]:
        """
        Retrieve all results from a completed search job.

        Args:
            job_uuid: UUID of the search job
            page_size: Number of results per page

        Returns:
            List of events

        Raises:
            requests.HTTPError: If an API call fails after retries
        """
        results: list[dict[str, Any]] = []
        offset = 0
        total: int | None = None

        while total is None or offset < total:
            data = self._get_search_job_events_page(job_uuid, page_size, offset)
            items = data.get("items", [])

            if not items:
                if len(results) < data.get("total", 0):
                    self.log(
                        "Fetched fewer results than expected",
                        level="warning",
                        fetched=len(results),
                        total=data.get("total", 0),
                        job_uuid=job_uuid,
                    )
                break

            results.extend(items)
            if total is None:
                total = data.get("total", 0)
            offset += page_size

        return results

    def _fetch_alert_events(
        self,
        alert: dict[str, Any],
        fetch_all: bool,
        previous_state: dict[str, Any] | None,
        max_events: int,
    ) -> list[dict[str, Any]] | None:
        """
        Fetch events from an alert using the async search job API.

        Returns:
            List of events, or None if API call failed
        """
        alert_short_id = alert.get("short_id")
        alert_uuid = alert.get("uuid")
        first_seen_at = alert.get("first_seen_at")
        last_seen_at = alert.get("last_seen_at")

        if not alert_short_id or not first_seen_at or not last_seen_at:
            self.log(message="Alert missing required fields for event fetching", level="error", alert_uuid=alert_uuid)
            return None

        # Determine time range
        if fetch_all:
            earliest_time = first_seen_at
        elif previous_state and previous_state.get("last_triggered_at"):
            earliest_time = previous_state["last_triggered_at"]
        else:
            earliest_time = first_seen_at

        # Run async search job pipeline
        job_uuid = self._trigger_event_search_job(alert_short_id, earliest_time, last_seen_at, max_events)

        if not self._wait_for_search_job(job_uuid):
            self.log(message="Search job timed out", level="error", alert_uuid=alert_uuid, job_uuid=job_uuid)
            return None

        return self._get_search_job_results(job_uuid)

    def _get_total_event_count(self, alert: dict[str, Any]) -> int | None:
        """
        Get total count of events for an alert using the search job API.

        Triggers a search job with limit=1 to get only the total count.

        Args:
            alert: Alert data dictionary (must contain short_id, first_seen_at, last_seen_at)

        Returns:
            Total number of events, or None if API call failed
        """
        alert_uuid = alert.get("uuid")
        alert_short_id = alert.get("short_id")
        first_seen_at = alert.get("first_seen_at")
        last_seen_at = alert.get("last_seen_at")

        if not alert_short_id or not first_seen_at or not last_seen_at:
            self.log(message="Alert missing required fields for event counting", level="error", alert_uuid=alert_uuid)
            return None

        try:
            job_uuid = self._trigger_event_search_job(alert_short_id, first_seen_at, last_seen_at, limit=1)

            if not self._wait_for_search_job(job_uuid):
                self.log(message="Search job timed out for event counting", level="error", alert_uuid=alert_uuid)
                return None

            data = self._get_search_job_events_page(job_uuid, limit=1, offset=0)
            return data.get("total", 0)

        except Exception as e:
            self.log_exception(e, message="Failed to get event count", alert_uuid=alert_uuid)
            return None

    def _cleanup_old_states(self) -> None:
        """Clean up state entries for old alerts (runs at most once per day)."""
        now = datetime.now(timezone.utc)

        if self._last_cleanup and (now - self._last_cleanup).total_seconds() < 86400:
            return

        if not self.state_manager:
            return

        config = self.validated_config
        cutoff_date = now - timedelta(days=config.state_cleanup_days)

        try:
            removed = self.state_manager.cleanup_old_states(cutoff_date)
            remaining_alerts = self.state_manager.get_all_alerts()
            STATE_SIZE.set(len(remaining_alerts))

            # Purge locks for alerts no longer in state to prevent memory leak.
            # Only delete locks that are not currently acquired to avoid race conditions.
            with self._locks_lock:
                stale_lock_keys = set(self._alert_locks.keys()) - set(remaining_alerts.keys())
                purged = 0
                for key in stale_lock_keys:
                    if not self._alert_locks[key].locked():
                        del self._alert_locks[key]
                        purged += 1

            if removed > 0 or purged > 0:
                self.log(
                    message=f"State cleanup: removed {removed} entries, purged {purged} locks",
                    level="info",
                    removed_count=removed,
                    purged_locks=purged,
                )

            self._last_cleanup = now
        except Exception as exp:
            self.log_exception(exp, message="Failed to cleanup old states")
