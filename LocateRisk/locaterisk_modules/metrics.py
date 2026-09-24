from prometheus_client import Counter, Histogram

# Declare module-specific prometheus metrics
prom_namespace = "symphony_module_locaterisk"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed from the LocateRisk scan report",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

# Declare common prometheus metrics
prom_namespace_common = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace_common,
    labelnames=["intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace_common,
    labelnames=["intake_key"],
)
