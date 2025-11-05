"""Contains the prometheus metrics for the connector."""

from prometheus_client import Counter, Gauge, Histogram

# Declare common prometheus metrics
prom_azure_namespace = "symphony_module_azure"
prom_namespace = "symphony_module_common"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages consumed from the event_hub",
    namespace=prom_azure_namespace,
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

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

MESSAGES_AGE = Gauge(
    name="messages_age",
    documentation="The age of messages seen",
    namespace=prom_azure_namespace,
    labelnames=["intake_key"],
)
