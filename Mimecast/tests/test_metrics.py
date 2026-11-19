from mimecast_modules import metrics


def test_metrics_are_declared_with_expected_namespaces() -> None:
    assert metrics.prom_namespace_ubika == "symphony_module_mimecast"
    assert metrics.prom_namespace == "symphony_module_common"

    assert metrics.INCOMING_MESSAGES._name == "symphony_module_mimecast_collected_messages"
    assert metrics.OUTCOMING_EVENTS._name == "symphony_module_common_forwarded_events"
    assert metrics.EVENTS_LAG._name == "symphony_module_common_events_lags"
    assert metrics.FORWARD_EVENTS_DURATION._name == "symphony_module_common_events_forward_duration"
