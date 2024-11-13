from prometheus_client import Counter, Gauge, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_panda_security"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed",
    namespace=prom_namespace,
    labelnames=["type", "intake_id"],
)

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
    namespace=prom_namespace,
    labelnames=["type", "intake_id"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["type", "intake_id"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["type", "intake_id"],
)
