from prometheus_client import Counter, Gauge, Histogram

prom_namespace = "symphony_module_flare"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

TRUNCATED_EVENTS = Counter(
    name="truncated_events",
    documentation="Number of events whose biggest fields were cut to fit the intake size limit",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

DISCARDED_EVENTS = Counter(
    name="discarded_events",
    documentation="Number of events still above the intake size limit after cutting",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="events_forward_duration",
    documentation="Duration to collect and forward events from Flare",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
