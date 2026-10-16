class WorkdayError(Exception):
    """Base exception for Workday client errors"""

    pass


class WorkdayAuthError(WorkdayError):
    """Authentication/authorization errors"""

    pass


class WorkdayRateLimitError(WorkdayError):
    """Rate limit exceeded errors"""

    pass
