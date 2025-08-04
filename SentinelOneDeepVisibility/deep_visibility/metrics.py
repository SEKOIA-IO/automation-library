"""All necessary metrics"""

from prometheus_client import Counter


prom_namespace = "symphony_module_sentinelone_dv"


DISCARDED_EVENTS = Counter(
    name="discarded_events",
    documentation="Number of events discarded from the colect",
    namespace=prom_namespace,
    labelnames=["intake_key"],
)
