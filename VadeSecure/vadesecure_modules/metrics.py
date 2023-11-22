from prometheus_client import Histogram

# Declare common prometheus metrics
prom_namespace = "symphony_module_common"

EVENTS_LAG = Histogram(
    name="events_lags",
    documentation="The delay, in seconds, from the date of the last event",
    namespace=prom_namespace,
    labelnames=["tenant_id"],
)
