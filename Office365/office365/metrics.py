from prometheus_client import Counter, Gauge, Histogram

# Declare prometheus metrics
prom_namespace = "symphony_module_common"

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

O365_API_FAILURES = Counter(
    name="o365_api_failures",
    documentation="Number of failed calls to the Office 365 Management API",
    namespace=prom_namespace,
    labelnames=["intake_key", "status", "operation"],
)

AUTH_FAILURES = Counter(
    name="o365_auth_failures",
    documentation="Number of failed authentications against Microsoft Entra ID",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)

NETWORK_FAILURES = Counter(
    name="o365_network_failures",
    documentation="Number of network/transport errors when talking to Microsoft",
    namespace=prom_namespace,
    labelnames=["intake_key", "exc_type"],
)
