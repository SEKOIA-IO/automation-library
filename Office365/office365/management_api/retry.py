import aiohttp
from tenacity import RetryCallState, wait_exponential

from .constants import OFFICE365_RETRY_AFTER_MAX_SECONDS, OFFICE365_RETRYABLE_STATUS_CODES
from .errors import FailedToGetO365AuditContent
from .logging import get_logger

logger = get_logger()

_exponential_wait = wait_exponential(multiplier=2, max=60)


def is_transient_content_error(error: BaseException) -> bool:
    """Tell if the download of an audit content failed on a transient error (HTTP or transport)"""
    if isinstance(error, FailedToGetO365AuditContent):
        return error.context.get("status_code") in OFFICE365_RETRYABLE_STATUS_CODES

    return isinstance(error, (aiohttp.ClientError, TimeoutError))


def wait_content_retry(retry_state: RetryCallState) -> float:
    """Wait for the delay asked by the `Retry-After` header (capped), or back off exponentially"""
    error = retry_state.outcome.exception() if retry_state.outcome else None
    retry_after: str | None = getattr(error, "context", {}).get("retry_after")

    if retry_after is not None:
        try:
            return min(float(retry_after), OFFICE365_RETRY_AFTER_MAX_SECONDS)
        except ValueError:  # an HTTP-date instead of seconds
            pass

    return _exponential_wait(retry_state)


def log_content_retry(retry_state: RetryCallState) -> None:
    """Log a failed attempt to download an audit content before the next retry"""
    error = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Failed to get the audit content, retrying",
        attempt=retry_state.attempt_number,
        status_code=getattr(error, "context", {}).get("status_code"),
        error=type(error).__name__ if error else None,
    )
