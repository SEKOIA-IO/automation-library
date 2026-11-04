from prometheus_client import Counter, Gauge, Histogram

prom_namespace_secuserve = "symphony_module_secuserve"

INCOMING_MESSAGES = Counter(
    name="collected_messages",
    documentation="Number of messages collected from e-securemail",
    namespace=prom_namespace_secuserve,
    labelnames=["intake_key"],
)

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
    documentation="Duration to collect and forward events from e-securemail",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
