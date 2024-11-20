"""All necessary metrics."""

from prometheus_client import Counter, Gauge, Histogram

# Declare common prometheus metrics
prom_aws_namespace = "symphony_module_aws"
prom_namespace = "symphony_module_common"


INCOMING_EVENTS = Counter(
    name="collected_events",
    documentation="Number of collected events from AWS S3",
    namespace=prom_aws_namespace,
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

MESSAGES_AGE = Histogram(
    name="messages_age",
    documentation="The age of messages seen",
    namespace=prom_aws_namespace,
    labelnames=["intake_key"],
)

DISCARDED_EVENTS = Counter(
    name="discarded_events",
    documentation="Number of events discarded from the collect",
    namespace=prom_aws_namespace,
    labelnames=["intake_key"],
)
