import pytest
from prometheus_client import REGISTRY

from netskope_modules.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


def test_incoming_messages_counter():
    before = REGISTRY.get_sample_value("symphony_module_common_collected_messages_total", {"intake_key": "test-in"})

    INCOMING_MESSAGES.labels(intake_key="test-in").inc(2)

    assert (
        REGISTRY.get_sample_value("symphony_module_common_collected_messages_total", {"intake_key": "test-in"})
        == (before or 0) + 2
    )


@pytest.mark.parametrize(
    "metric,sample_name",
    [
        (OUTCOMING_EVENTS, "symphony_module_common_forwarded_events_total"),
        (EVENTS_LAG, "symphony_module_common_events_lags"),
        (FORWARD_EVENTS_DURATION, "symphony_module_common_forward_events_duration_count"),
    ],
)
def test_event_metrics_are_labelled_by_intake_key_and_type(metric, sample_name):
    labels = {"intake_key": "test-metrics", "type": "alert-dlp"}
    child = metric.labels(**labels)

    if metric is EVENTS_LAG:
        child.set(42)
        expected = 42
    elif metric is FORWARD_EVENTS_DURATION:
        before = REGISTRY.get_sample_value(sample_name, labels) or 0
        child.observe(1.5)
        expected = before + 1
    else:
        before = REGISTRY.get_sample_value(sample_name, labels) or 0
        child.inc()
        expected = before + 1

    assert REGISTRY.get_sample_value(sample_name, labels) == expected
