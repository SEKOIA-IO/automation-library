import pytest

from akamai_modules import metrics


@pytest.mark.parametrize(
    "metric,expected_name,expected_type,expected_labelnames",
    [
        (
            metrics.INCOMING_MESSAGES,
            "symphony_module_akamai_collected_messages",
            "counter",
            ("intake_key", "scalable_horizontally", "scalable_vertically"),
        ),
        (
            metrics.OUTCOMING_EVENTS,
            "symphony_module_common_forwarded_events",
            "counter",
            ("intake_key", "scalable_horizontally", "scalable_vertically"),
        ),
        (
            metrics.FORWARD_EVENTS_DURATION,
            "symphony_module_common_forward_events_duration",
            "histogram",
            ("intake_key", "scalable_horizontally", "scalable_vertically"),
        ),
        (
            metrics.EVENTS_LAG,
            "symphony_module_common_events_lags",
            "gauge",
            ("intake_key", "scalable_horizontally", "scalable_vertically"),
        ),
    ],
)
def test_metric_declaration(metric, expected_name, expected_type, expected_labelnames):
    family = list(metric.collect())[0]

    assert family.name == expected_name
    assert family.type == expected_type
    assert metric._labelnames == expected_labelnames
