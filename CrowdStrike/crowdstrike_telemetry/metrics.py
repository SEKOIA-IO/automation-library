from prometheus_client import Counter

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

DISCARDED_EVENTS = Counter(
    name="discarded_events",
    documentation="Number of events discarded from the collect",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
