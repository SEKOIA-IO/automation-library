from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sekoia_automation.trigger import Trigger


class AlertEventsThresholdConfiguration(BaseModel):
    """
    Configuration for the Alert Events Threshold Trigger.

    Note: This is an internal module. Authentication credentials are automatically
    injected by the Sekoia.io backend. This trigger provides alert data to downstream
    playbook actions (ITSM, notifications, etc.) and does NOT re-inject events.
    """

    # Internal parameters (injected by backend, not exposed to users)
    # Note: These are NOT intake-related parameters. The trigger does not re-inject
    # events into an intake. These credentials are only for reading alert data.
    base_url: str = Field(
        default="",  # Injected by backend
        description="[INTERNAL] Sekoia.io API base URL (automatically provided)",
        exclude=True,  # Hidden from user configuration
    )

    api_key: str = Field(
        default="",  # Injected by backend
        description="[INTERNAL] API key for reading alert data (automatically provided)",
        secret=True,
        exclude=True,  # Hidden from user configuration
    )

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

    @field_validator("enable_volume_threshold", "enable_time_threshold")
    @classmethod
    def validate_at_least_one_threshold(cls, v, info):
        """Ensure at least one threshold is enabled."""
        values = info.data
        if "enable_volume_threshold" in values and "enable_time_threshold" in values:
            if not values["enable_volume_threshold"] and not values["enable_time_threshold"]:
                raise ValueError("At least one threshold must be enabled")
        return v