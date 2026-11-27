OFFICE365_AUTHORITY_DEFAULT = "https://login.microsoftonline.com/common"
OFFICE365_URL_BASE = "https://manage.office.com/api/v1.0/{tenant_id}/activity/feed"
OFFICE365_ACTIVE_SUBSCRIPTION_STATUS = "enabled"
# Transient HTTP errors from the Office 365 Management API that are worth retrying
OFFICE365_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# Upper bound of the delay asked by a `Retry-After` header, as audit contents are downloaded one by one
OFFICE365_RETRY_AFTER_MAX_SECONDS = 120
