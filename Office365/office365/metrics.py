from prometheus_client import Counter, Gauge, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_common"
prom_o365_namespace = "symphony_module_o365"

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

CHECKPOINT_PERSISTENCE_FAILURES = Counter(
    name="checkpoint_persistence_failures",
    documentation="Number of failed checkpoint persistence attempts",
    namespace=prom_o365_namespace,
    labelnames=["intake_key"],
)
