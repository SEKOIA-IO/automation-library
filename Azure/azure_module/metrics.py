from prometheus_client import Counter, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_azure"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed from the event_hub",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

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
