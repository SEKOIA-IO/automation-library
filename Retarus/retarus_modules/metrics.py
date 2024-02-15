from prometheus_client import Counter

# Declare prometheus metrics
prom_namespace = "symphony_module_retarus"

OUTGOING_EVENTS = Counter(
    name="forwarded_events",
    documentation="Number of events forwarded to Sekoia.io",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
