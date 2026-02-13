from prometheus_client import Counter, Gauge, Histogram

events_collected = Counter(
    "anozrway_historical_events_collected",
    "Total number of Anozrway historical records collected",
)

events_forwarded = Counter(
    "anozrway_historical_events_forwarded",
    "Total number of Anozrway historical records forwarded to intake",
)

events_duplicated = Counter(
    "anozrway_historical_events_duplicated",
    "Total number of duplicate Anozrway historical records filtered",
)

api_requests = Counter(
    "anozrway_api_requests",
    "Total number of Anozrway API requests",
    ["endpoint", "status_code"],
)

api_request_duration = Histogram(
    "anozrway_api_request_duration_seconds",
    "Anozrway API request duration in seconds",
    ["endpoint"],
)

checkpoint_age = Gauge(
    "anozrway_checkpoint_age_seconds",
    "Age of the last checkpoint in seconds",
)
