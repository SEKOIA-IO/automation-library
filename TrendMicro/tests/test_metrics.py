from trendmicro_modules.metrics import (
    EVENTS_LAG,
    FORWARD_EVENTS_DURATION,
    INCOMING_MESSAGES,
    OUTCOMING_EVENTS,
)


def test_metrics_are_declared_with_expected_names():
    assert INCOMING_MESSAGES._name == "symphony_module_trend_micro_collected_messages"
    assert OUTCOMING_EVENTS._name == "symphony_module_common_forwarded_events"
    assert FORWARD_EVENTS_DURATION._name == "symphony_module_common_forward_events_duration"
    assert EVENTS_LAG._name == "symphony_module_common_events_lags"
