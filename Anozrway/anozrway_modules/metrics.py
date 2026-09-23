from prometheus_client import Counter, Gauge, Histogram

# Standard metrics following the symphony_module_common convention
prom_namespace = "symphony_module_common"

events_collected = Counter(
    name="collected_messages",
    documentation="Total number of Anozrway historical records collected",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

events_forwarded = Counter(
    name="forwarded_events",
    documentation="Total number of Anozrway historical records forwarded to intake",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

events_duplicated = Counter(
    name="duplicated_events",
    documentation="Total number of duplicate Anozrway historical records filtered",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

api_request_duration = Histogram(
    name="forward_events_duration",
    documentation="Duration to collect and forward events",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

checkpoint_age = Gauge(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

# Module-specific metrics
prom_namespace_anozrway = "symphony_module_anozrway"

api_requests = Counter(
    name="api_requests",
    documentation="Total number of Anozrway API requests",
    namespace=prom_namespace_anozrway,
    labelnames=["intake_key", "endpoint", "status_code"],
)
