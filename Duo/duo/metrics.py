from prometheus_client import Counter, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_netskope"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed",
    namespace=prom_namespace,
    labelnames=["intake_key", "type"],
)

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace,
    labelnames=["intake_key", "type"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["intake_key", "type"],
)
