from prometheus_client import Counter, Gauge

# Declare prometheus metrics
prom_namespace_crowdstrike = "symphony_module_crowdstrike"

INCOMING_DETECTIONS = Counter(
    name="collected_detections",
    documentation="Number of detections collected from Crowdstrike",
    namespace=prom_namespace_crowdstrike,
    labelnames=["intake_key", "scalable_horizontally", "scalable_vertically"],
)

INCOMING_VERTICLES = Counter(
    name="collected_verticles",
    documentation="Number of detections collected from Crowdstrike",
    namespace=prom_namespace_crowdstrike,
    labelnames=["intake_key", "scalable_horizontally", "scalable_vertically"],
)

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
    namespace=prom_namespace,
    labelnames=["intake_key", "scalable_horizontally", "scalable_vertically"],
)

EVENTS_LAG = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key", "stream", "scalable_horizontally", "scalable_vertically"],
)
