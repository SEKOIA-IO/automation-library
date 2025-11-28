from prometheus_client import Counter, Gauge, Histogram

# Event metrics
events_collected = Counter(
    "workday_activity_logs_collected_total",
    "Total number of activity logs collected",
)

events_forwarded = Counter(
    "workday_activity_logs_forwarded_total",
    "Total number of activity logs forwarded to intake",
)

events_duplicated = Counter(
    "workday_activity_logs_duplicated_total",
    "Total number of duplicate activity logs filtered",
)

# API metrics
api_requests = Counter("workday_api_requests_total", "Total number of API requests", ["endpoint", "status_code"])

api_request_duration = Histogram(
    "workday_api_request_duration_seconds", "API request duration in seconds", ["endpoint"]
)

# Checkpoint metrics
checkpoint_age = Gauge("workday_checkpoint_age_seconds", "Age of the last checkpoint in seconds")
