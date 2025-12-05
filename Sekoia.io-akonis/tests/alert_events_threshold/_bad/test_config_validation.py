import pytest
from pydantic import ValidationError
from sekoiaio.triggers.alert_events_threshold import AlertEventsThresholdConfiguration


def test_validation_both_thresholds_disabled():
    with pytest.raises(ValidationError):
        AlertEventsThresholdConfiguration(
            enable_time_threshold=False,
            enable_volume_threshold=False
        )


def test_validation_filter_conflict():
    with pytest.raises(ValidationError):
        AlertEventsThresholdConfiguration(
            rule_filter="A",
            rule_names_filter=["A"]
        )


def test_validation_cleanup_less_than_time_window():
    with pytest.raises(ValidationError):
        AlertEventsThresholdConfiguration(
            time_window_hours=24,
            state_cleanup_days=0  # < 24h window
        )
