from prometheus_client import Counter, Gauge, Histogram

# Common metrics, shared across the automation library. Names, namespace and the `intake_key` label
# must stay aligned with the other connectors: the platform dashboards and alerting are built on
# them, so a connector using its own naming is effectively invisible to standard monitoring.
prom_namespace = "symphony_module_common"

OUTCOMING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
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
    name="forward_events_duration",
    documentation="Duration to collect and forward events from Workday",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

# Workday-specific metrics
prom_namespace_workday = "symphony_module_workday"

INCOMING_EVENTS = Counter(
    name="collected_events",
    documentation="Number of events collected from the Workday Activity Logging API",
    namespace=prom_namespace_workday,
    labelnames=["intake_key"],
)

EVENTS_DUPLICATED = Counter(
    name="duplicated_events",
    documentation="Number of duplicate activity logs filtered out before forwarding",
    namespace=prom_namespace_workday,
    labelnames=["intake_key"],
)

EVENTS_TRUNCATED = Counter(
    name="truncated_windows",
    documentation="Number of collection cycles where the time window saturated the instancesReturned "
    "pool (events may have been truncated by the API)",
    namespace=prom_namespace_workday,
    labelnames=["intake_key"],
)

CHECKPOINT_AGE = Gauge(
    name="checkpoint_age_seconds",
    documentation="Age, in seconds, of the collection checkpoint",
    namespace=prom_namespace_workday,
    labelnames=["intake_key"],
)

API_REQUESTS = Counter(
    name="api_requests",
    documentation="Number of requests sent to the Workday API",
    namespace=prom_namespace_workday,
    labelnames=["intake_key", "endpoint", "status_code"],
)

API_REQUEST_DURATION = Histogram(
    name="api_request_duration_seconds",
    documentation="Duration of the requests sent to the Workday API",
    namespace=prom_namespace_workday,
    labelnames=["intake_key", "endpoint"],
)
