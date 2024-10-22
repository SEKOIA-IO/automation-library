from prometheus_client import Counter, Gauge, Histogram

# Declare google prometheus metrics
prom_namespace_tehtris = "symphony_module_tehtris"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages collected from Tehtris",
    namespace=prom_namespace_tehtris,
    labelnames=["intake_key"],
)

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
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
    documentation="Duration to collect and forward events from Tehtris",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
