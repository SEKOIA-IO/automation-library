#!/usr/bin/env bash
set -u

tests=(
    "test_alert_events_threshold.py::test_first_occurrence_triggers_immediately"
    "test_alert_events_threshold.py::test_volume_threshold_trigger"
    "test_alert_events_threshold.py::test_time_threshold_trigger"
    "test_alert_events_threshold.py::test_rule_names_filter_matches"
    "test_alert_events_threshold.py::test_malformed_event_count_response"
    "test_alert_events_threshold.py::test_api_timeout_with_retry"
    #"test_alert_events_threshold.py::test_multiple_notifications_same_alert_quick_succession"
    #"test_alert_events_threshold.py::test_state_cleanup_during_active_operations"
    #"test_alert_events_threshold.py::test_multiple_alerts_with_rate_limiting"
    #"test_alert_events_threshold.py::test_state_manager_cleanup"
    #"test_alert_events_threshold.py::test_state_file_corruption_recovery"
    #"test_alert_events_threshold.py::test_alert_without_events_count_field"
    #"test_alert_events_threshold.py::test_metrics_updated_on_trigger"
    #"test_alert_events_threshold.py::test_full_workflow_volume_threshold"
)

failed=0

for t in "${tests[@]}"; do
    echo "=== Running: $t ==="
    poetry run pytest -v "$t" || { echo ">>> TEST FAILED: $t" >&2; failed=1; }
done

exit $failed