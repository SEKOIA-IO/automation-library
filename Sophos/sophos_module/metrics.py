from prometheus_client import Counter, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_sophos"

INCOMING_EVENTS = Counter(
    name="collected_events",
    documentation="Number of events collected from Sophos",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events from Sophos",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
