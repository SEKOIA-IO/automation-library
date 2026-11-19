from prometheus_client import Counter, Gauge, Histogram

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events from eventhub",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

FETCH_EVENTS_DURATION = Histogram(
    name="fetch_events_duration",
    documentation="Duration to fetch one page of events from the Cato events feed",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

PUSH_EVENTS_DURATION = Histogram(
    name="push_events_duration",
    documentation="Duration to push one page of events to the intake",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
