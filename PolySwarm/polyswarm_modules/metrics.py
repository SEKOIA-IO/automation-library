from prometheus_client import Counter, Gauge, Histogram

# Declare common prometheus metrics, under the names and namespace every
# connector in the library reports, so the platform charts them without any
# per module configuration.
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to SEKOIA.IO",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

FORWARD_EVENTS_DURATION = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

COLLECTED_EVENTS = Counter(
    name="collected_events",
    documentation="Number of collected events dropped before forwarding, by reason",
    namespace=prom_namespace,
    labelnames=["intake_key", "reason"],
)
