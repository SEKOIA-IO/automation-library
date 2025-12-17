import uuid
from posixpath import join as urljoin

import orjson
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

from sekoiaio.utils import user_agent

from .base import _SEKOIANotificationBaseTrigger


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
            "rule": {"name": alert["rule"]["name"], "uuid": alert["rule"]["uuid"]},
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
            "rule": {"name": alert["rule"]["name"], "uuid": alert["rule"]["uuid"]},
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

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator

from .helpers.state_manager import AlertStateManager
from .metrics import EVENTS_FORWARDED, EVENTS_FILTERED, THRESHOLD_CHECKS, STATE_SIZE


class AlertEventsThresholdConfiguration(BaseModel):
    """
    Configuration for the Alert Events Threshold Trigger.
    """

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

    check_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Polling interval for checking thresholds (10s - 1h)",
    )

    state_cleanup_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Remove state entries for alerts older than N days",
    )

    @model_validator(mode='after')
    def validate_at_least_one_threshold(self):
        """Ensure at least one threshold is enabled."""
        if not self.enable_volume_threshold and not self.enable_time_threshold:
            raise ValueError("At least one threshold must be enabled")
        return self

    @model_validator(mode='after')
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
    """

    # Handle only alert updates
    HANDLED_EVENT_SUB_TYPES = [("alert", "updated")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager: Optional[AlertStateManager] = None
        self._last_cleanup: Optional[datetime] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of state manager."""
        if not self._initialized:
            self.log(message="Initializing AlertEventsThresholdTrigger", level="debug")
            state_path = self._data_path / "alert_thresholds_state.json"
            self.log(message=f"State file path: {state_path}", level="debug")

            try:
                self.state_manager = AlertStateManager(state_path, logger=self.log)
                self._initialized = True
                self.log(
                    message="AlertEventsThresholdTrigger initialized successfully",
                    level="info",
                    state_path=str(state_path)
                )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to initialize AlertEventsThresholdTrigger",
                    state_path=str(state_path)
                )
                raise

    def handle_event(self, message):
        """
        Handle alert update messages with threshold evaluation.

        This method overrides the parent class to add threshold logic before
        triggering the playbook.
        """
        self.log(message="Received event message", level="debug", message_type=message.get("type"), message_action=message.get("action"))

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
                handled_types=str(self.HANDLED_EVENT_SUB_TYPES)
            )
            return

        # Extract alert UUID
        alert_uuid: str = alert_attrs.get("uuid", "")
        if not alert_uuid:
            self.log(
                message="Notification missing alert UUID",
                level="warning",
                message_attributes=str(alert_attrs)
            )
            return

        self.log(message="Processing alert update", level="debug", alert_uuid=alert_uuid)

        try:
            # Reuse parent's method for API retrieval
            self.log(message=f"Fetching alert {alert_uuid} from API", level="debug")
            alert = self._retrieve_alert_from_alertapi(alert_uuid)
            self.log(
                message=f"Successfully retrieved alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                short_id=alert.get("short_id"),
                events_count=alert.get("events_count", 0),
                rule_name=alert.get("rule", {}).get("name")
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to fetch alert from Alert API",
                alert_uuid=alert_uuid
            )
            return

        # Reuse parent's rule filtering logic
        if not self._should_process_alert(alert):
            EVENTS_FILTERED.labels(reason="rule_filter").inc()
            self.log(
                message=f"Alert {alert.get('short_id')} filtered out by rule filter",
                level="debug",
                alert_uuid=alert_uuid,
                rule_name=alert.get("rule", {}).get("name"),
                rule_uuid=alert.get("rule", {}).get("uuid")
            )
            return

        self.log(message=f"Alert {alert.get('short_id')} passed rule filter", level="debug", alert_uuid=alert_uuid)

        # Load previous state for this alert
        try:
            previous_state = self.state_manager.get_alert_state(alert_uuid)
            self.log(
                message=f"Loaded previous state for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                has_previous_state=previous_state is not None,
                previous_count=previous_state.get("last_triggered_event_count") if previous_state else 0
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to load previous state, continuing without it",
                alert_uuid=alert_uuid
            )
            previous_state = None

        # Evaluate thresholds
        try:
            self.log(message=f"Evaluating thresholds for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
            should_trigger, context = self._evaluate_thresholds(alert, previous_state)
            self.log(
                message=f"Threshold evaluation completed for alert {alert.get('short_id')}",
                level="debug",
                alert_uuid=alert_uuid,
                should_trigger=should_trigger,
                trigger_context=str(context)
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to evaluate thresholds",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id")
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
                previous_count=context.get("previous_count")
            )
            return

        # Update state before triggering
        try:
            self.log(message=f"Updating state for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
            self.state_manager.update_alert_state(
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id"),
                rule_uuid=alert.get("rule", {}).get("uuid"),
                rule_name=alert.get("rule", {}).get("name"),
                event_count=alert.get("events_count", 0),
                previous_version=previous_state.get("version") if previous_state else None,
            )
            self.log(message=f"State updated successfully for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to update alert state",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id")
            )
            # Continue despite state update failure

        # Periodic cleanup of old states
        try:
            self._cleanup_old_states()
        except Exception as exp:
            self.log_exception(exp, message="Failed to cleanup old states, continuing")
            # Continue despite cleanup failure

        # Reuse parent's method for creating event payload
        try:
            self.log(message=f"Sending threshold event for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
            self._send_threshold_event(alert, event_type, context)
            self.log(message=f"Threshold event sent successfully for alert {alert.get('short_id')}", level="debug", alert_uuid=alert_uuid)
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to send threshold event",
                alert_uuid=alert_uuid,
                alert_short_id=alert.get("short_id")
            )
            return

        EVENTS_FORWARDED.labels(reason=context["reason"]).inc()

        self.log(
            message=f"Triggered for alert {alert.get('short_id')}: {context['new_events']} new events ({context['reason']})",
            level="info",
            alert_uuid=alert_uuid,
            alert_short_id=alert.get("short_id"),
            new_events=context["new_events"],
            trigger_reason=context["reason"],
            current_count=context["current_count"],
            previous_count=context["previous_count"]
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
        rule_filter = self.configuration.get("rule_filter")
        rule_names_filter = self.configuration.get("rule_names_filter")

        # No filters: accept all
        if not rule_filter and not rule_names_filter:
            self.log(message="No rule filters configured, accepting all alerts", level="debug")
            return True

        rule_name = alert.get("rule", {}).get("name")
        rule_uuid = alert.get("rule", {}).get("uuid")

        # Single rule filter
        if rule_filter:
            matches = rule_name == rule_filter or rule_uuid == rule_filter
            self.log(
                message=f"Single rule filter check: {matches}",
                level="debug",
                configured_filter=rule_filter,
                alert_rule_name=rule_name,
                alert_rule_uuid=rule_uuid
            )
            return matches

        # Multiple rule names filter
        if rule_names_filter:
            matches = rule_name in rule_names_filter
            self.log(
                message=f"Multiple rule names filter check: {matches}",
                level="debug",
                configured_filters=str(rule_names_filter),
                alert_rule_name=rule_name
            )
            return matches

        return True

    def _send_threshold_event(self, alert: dict[str, Any], event_type: str, context: dict[str, Any]):
        """
        Send event to playbook with threshold context.

        This extends the parent's event creation with threshold-specific information.

        Args:
            alert: Alert data dictionary
            event_type: Type of the event
            context: Threshold evaluation context
        """
        import uuid as uuid_lib

        alert_short_id = alert.get("short_id")
        alert_uuid = alert.get("uuid")

        self.log(
            message=f"Creating threshold event for alert {alert_short_id}",
            level="debug",
            alert_uuid=alert_uuid,
            event_type=event_type
        )

        # Create work directory for alert data
        try:
            work_dir = self._data_path.joinpath("sekoiaio_alert_threshold").joinpath(str(uuid_lib.uuid4()))
            alert_path = work_dir.joinpath("alert.json")
            work_dir.mkdir(parents=True, exist_ok=True)
            self.log(message=f"Created work directory: {work_dir}", level="debug")
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to create work directory",
                alert_uuid=alert_uuid,
                alert_short_id=alert_short_id
            )
            raise

        try:
            with alert_path.open("w") as fp:
                fp.write(orjson.dumps(alert).decode("utf-8"))
            self.log(message=f"Wrote alert data to {alert_path}", level="debug")
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to write alert data to file",
                alert_path=str(alert_path),
                alert_uuid=alert_uuid
            )
            raise

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
            "rule": {"name": alert["rule"]["name"], "uuid": alert["rule"]["uuid"]},
            "last_seen_at": alert.get("last_seen_at"),
            "first_seen_at": alert.get("first_seen_at"),
            "events_count": alert.get("events_count", 0),
            # Add threshold-specific context
            "trigger_context": {
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "trigger_type": "alert_events_threshold",
                **context,
            },
        }

        self.log(
            message=f"Built event payload for alert {alert_short_id}",
            level="debug",
            event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
            directory=directory
        )

        try:
            self.send_event(
                event_name=f"Sekoia.io Alert Threshold: {alert_short_id}",
                event=event,
                directory=directory,
                remove_directory=True,
            )
            self.log(
                message=f"Event sent successfully for alert {alert_short_id}",
                level="info",
                alert_uuid=alert_uuid
            )
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to send event to playbook",
                alert_uuid=alert_uuid,
                alert_short_id=alert_short_id,
                event_name=f"Sekoia.io Alert Threshold: {alert_short_id}"
            )
            raise

    def _evaluate_thresholds(
        self,
        alert: dict[str, Any],
        previous_state: Optional[dict[str, Any]],
    ) -> tuple[bool, dict[str, Any]]:
        """
        Evaluate whether alert meets triggering thresholds.

        Args:
            alert: Current alert data
            previous_state: Previous state for this alert (if any)

        Returns:
            Tuple of (should_trigger, trigger_context)
        """
        alert_uuid = alert["uuid"]
        current_event_count = alert.get("events_count", 0)

        self.log(
            message="Starting threshold evaluation",
            level="debug",
            alert_uuid=alert_uuid,
            current_event_count=current_event_count,
            has_previous_state=previous_state is not None
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
                current_event_count=current_event_count
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
            new_events=new_events
        )

        # No new events: skip
        if new_events <= 0:
            THRESHOLD_CHECKS.labels(triggered="false").inc()
            self.log(
                message="No new events since last trigger, skipping",
                level="debug",
                alert_uuid=alert_uuid,
                previous_count=previous_count,
                current_count=current_event_count
            )
            return False, {"reason": "no_new_events"}

        trigger_reasons = []

        # Volume-based threshold
        enable_volume = self.configuration.get("enable_volume_threshold", True)
        event_count_threshold = self.configuration.get("event_count_threshold", 100)

        self.log(
            message="Checking volume-based threshold",
            level="debug",
            alert_uuid=alert_uuid,
            enable_volume=enable_volume,
            event_count_threshold=event_count_threshold,
            new_events=new_events
        )

        if enable_volume and new_events >= event_count_threshold:
            trigger_reasons.append("volume_threshold")
            self.log(
                message=f"Volume threshold met: {new_events} >= {event_count_threshold}",
                level="debug",
                alert_uuid=alert_uuid
            )

        # Time-based threshold
        enable_time = self.configuration.get("enable_time_threshold", True)
        time_window_hours = self.configuration.get("time_window_hours", 1)

        self.log(
            message="Checking time-based threshold",
            level="debug",
            alert_uuid=alert_uuid,
            enable_time=enable_time,
            time_window_hours=time_window_hours
        )

        if enable_time:
            try:
                events_in_window = self._count_events_in_time_window(
                    alert_uuid,
                    time_window_hours,
                )
                self.log(
                    message=f"Events in time window: {events_in_window}",
                    level="debug",
                    alert_uuid=alert_uuid,
                    time_window_hours=time_window_hours,
                    events_in_window=events_in_window
                )
                if events_in_window > 0:
                    trigger_reasons.append("time_threshold")
                    self.log(
                        message=f"Time threshold met: {events_in_window} events in last {time_window_hours}h",
                        level="debug",
                        alert_uuid=alert_uuid
                    )
            except Exception as exp:
                self.log_exception(
                    exp,
                    message="Failed to check time-based threshold, skipping",
                    alert_uuid=alert_uuid,
                    time_window_hours=time_window_hours
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
            new_events=new_events
        )

        return should_trigger, context

    def _count_events_in_time_window(
        self,
        alert_uuid: str,
        hours: int,
    ) -> int:
        """
        Count events added to alert within the last N hours.

        Args:
            alert_uuid: UUID of the alert
            hours: Time window in hours

        Returns:
            Number of events in the time window
        """
        from posixpath import join as urljoin

        earliest_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        self.log(
            message=f"Counting events in time window for alert {alert_uuid}",
            level="debug",
            alert_uuid=alert_uuid,
            hours=hours,
            earliest_time=earliest_time.isoformat()
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

        self.log(
            message=f"Calling events API: {api_url}",
            level="debug",
            alert_uuid=alert_uuid,
            payload=str(payload)
        )

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)

            self.log(
                message=f"Events API response received",
                level="debug",
                alert_uuid=alert_uuid,
                status_code=response.status_code
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
                    error_content=str(error_content)
                )

            response.raise_for_status()
            data = response.json()
            event_count = data.get("total", 0)

            self.log(
                message=f"Successfully counted events in time window",
                level="debug",
                alert_uuid=alert_uuid,
                event_count=event_count,
                hours=hours
            )

            return event_count
        except requests.exceptions.Timeout as e:
            self.log(
                message=f"Timeout counting events for alert {alert_uuid}",
                level="error",
                alert_uuid=alert_uuid,
                timeout=30,
                error=str(e)
            )
            return 0  # Fail open: don't block on count errors
        except requests.exceptions.RequestException as e:
            self.log(
                message=f"Request error counting events for alert {alert_uuid}",
                level="error",
                alert_uuid=alert_uuid,
                error=str(e),
                error_type=type(e).__name__
            )
            return 0  # Fail open: don't block on count errors
        except Exception as e:
            self.log_exception(
                e,
                message=f"Failed to count events for alert {alert_uuid}",
                alert_uuid=alert_uuid
            )
            return 0  # Fail open: don't block on count errors

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
                seconds_since_last_cleanup=seconds_since_last
            )
            return

        self.log(message="Starting state cleanup", level="debug")

        state_cleanup_days = self.configuration.get("state_cleanup_days", 30)
        cutoff_date = now - timedelta(days=state_cleanup_days)

        self.log(
            message=f"Cleaning up states older than {state_cleanup_days} days",
            level="debug",
            state_cleanup_days=state_cleanup_days,
            cutoff_date=cutoff_date.isoformat()
        )

        try:
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
                    remaining_states=state_size
                )
            else:
                self.log(
                    message="State cleanup: no old entries to remove",
                    level="debug",
                    state_cleanup_days=state_cleanup_days,
                    remaining_states=state_size
                )

            self._last_cleanup = now
        except Exception as exp:
            self.log_exception(
                exp,
                message="Failed to cleanup old states",
                state_cleanup_days=state_cleanup_days
            )
            # Don't update _last_cleanup if cleanup failed, will retry next time
