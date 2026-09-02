from akamai_modules import metrics


def test_metrics_are_declared_with_expected_name_type_and_labels():
    expected = [
        (
            metrics.INCOMING_MESSAGES,
            "symphony_module_akamai_collected_messages",
            "counter",
            ("intake_key",),
        ),
        (
            metrics.OUTCOMING_EVENTS,
            "symphony_module_common_forwarded_events",
            "counter",
            ("intake_key",),
        ),
        (
            metrics.FORWARD_EVENTS_DURATION,
            "symphony_module_common_forward_events_duration",
            "histogram",
            ("intake_key",),
        ),
        (
            metrics.EVENTS_LAG,
            "symphony_module_common_events_lags",
            "gauge",
            ("intake_key",),
        ),
    ]

    for metric, expected_name, expected_type, expected_labelnames in expected:
        family = list(metric.collect())[0]

        assert family.name == expected_name
        assert family.type == expected_type
        assert metric._labelnames == expected_labelnames
