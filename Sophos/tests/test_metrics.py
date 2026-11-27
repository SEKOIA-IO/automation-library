from prometheus_client import Counter, Gauge, Histogram

from sophos_module.metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_EVENTS, OUTCOMING_EVENTS


def test_metrics_names_and_types():
    # names used by the Grafana dashboards: do not rename
    assert isinstance(INCOMING_EVENTS, Counter)
    assert INCOMING_EVENTS._name == "symphony_module_sophos_collected_events"
    assert isinstance(OUTCOMING_EVENTS, Counter)
    assert OUTCOMING_EVENTS._name == "symphony_module_common_forwarded_events"
    assert isinstance(FORWARD_EVENTS_DURATION, Histogram)
    assert FORWARD_EVENTS_DURATION._name == "symphony_module_common_forward_events_duration"
    assert isinstance(EVENTS_LAG, Gauge)
    assert EVENTS_LAG._name == "symphony_module_common_events_lags"


def test_metrics_labels():
    for metric in (INCOMING_EVENTS, OUTCOMING_EVENTS, FORWARD_EVENTS_DURATION, EVENTS_LAG):
        assert metric._labelnames == ("intake_key",)
