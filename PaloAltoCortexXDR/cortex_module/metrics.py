from prometheus_client import Counter, Histogram, Gauge

prom_namespace_cortex = "symphony_module_cortex"

INCOMING_EVENTS = Counter(
    name="collected_events",
    documentation="Number of events collected from Cortex",
    namespace=prom_namespace_cortex,
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
    documentation="Duration to collect and forward events from Darktrace",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
