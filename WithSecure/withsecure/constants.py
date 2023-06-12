from urllib.parse import urljoin

API_BASE_URL = "https://api.connect.withsecure.com"
API_TIMEOUT = 5
API_AUTH_SECONDS_BETWEEN_ATTEMPTS = 5
API_FETCH_EVENTS_PAGE_SIZE = 1000
API_AUTH_MAX_ATTEMPT = 5
API_SECURITY_EVENTS_URL = urljoin(API_BASE_URL, "/security-events/v1/security-events")
API_DEVICES_OPERATION_URL = urljoin(API_BASE_URL, "/devices/v1/operations")
API_LIST_DEVICES_URL = urljoin(API_BASE_URL, "/devices/v1/devices")
