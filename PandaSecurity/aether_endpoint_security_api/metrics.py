from prometheus_client import Counter, Histogram, Gauge

# Declare prometheus metrics
prom_namespace = "symphony_module_panda_security"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed",
    namespace=prom_namespace,
    labelnames=["type"],
)

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
    namespace=prom_namespace,
    labelnames=["type"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["type"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["type"],
)
