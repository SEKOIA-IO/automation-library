from prometheus_client import Counter, Gauge, Histogram

# Existing metrics...
# (EVENTS_LAG, OUTCOMING_EVENTS, etc.)

# New metrics for threshold trigger
THRESHOLD_CHECKS = Counter(
    "sekoiaio_alert_threshold_checks_total",
    "Total number of threshold checks performed",
    ["triggered"],
)

EVENTS_FILTERED = Counter(
    "sekoiaio_alert_events_filtered_total",
    "Total number of alert updates filtered out",
    ["reason"],
)

EVENTS_FORWARDED = Counter(
    "sekoiaio_alert_threshold_triggered_total",
    "Total number of alerts that met thresholds and triggered playbooks",
    ["reason"],
)

STATE_SIZE = Gauge(
    "sekoiaio_alert_threshold_state_size",
    "Number of alerts tracked in state",
)