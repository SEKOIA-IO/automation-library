from prometheus_client import Counter, Gauge, Histogram

# Declare google prometheus metrics
prom_namespace_beyondtrust = "symphony_module_beyondtrust"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages collected from BeyondTrust",
    namespace=prom_namespace_beyondtrust,
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
    documentation="Duration to collect and forward events from BeyondTrust",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
