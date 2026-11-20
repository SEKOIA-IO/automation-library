import time

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, InvalidHeader
from urllib3.exceptions import InvalidHeader as RetryHeaderError
from urllib3.response import HTTPResponse
from urllib3.util.retry import Retry as BaseRetry


class RetryDelayExceeded(InvalidHeader):
    """Preserve Microsoft backoff without blocking a short-lived action request."""

    def __init__(self, delay: float):
        super().__init__("Retry-After exceeds the 30-second request retry budget")
        self.retry_at = time.monotonic() + delay


class Retry(BaseRetry):
    """Customize retry behavior for Microsoft Graph API requests."""

    @staticmethod
    def parse_ratelimit_retry_after(ratelimit_retry_after: str) -> float | None:
        """Convert an absolute retry timestamp into a positive delay."""
        lower_bound = float(ratelimit_retry_after)

        delay = lower_bound - time.time()
        if delay > 0:
            return delay

        return None

    def get_retry_after(self, response: HTTPResponse) -> float | None:  # type: ignore
        """Return retry delay from supported rate-limit response headers."""

        # parse Retry-After header if defined
        retry_after = response.getheader("Retry-After")
        if retry_after:
            delay = self.parse_retry_after(retry_after)
            if delay > 30:
                raise RetryDelayExceeded(delay)
            return delay

        return None


def retry_deadline(exc: Exception) -> float | None:
    """Recover advertised backoff from adapter failures or non-retried HTTP responses."""
    if isinstance(exc, RetryDelayExceeded):
        return exc.retry_at
    # Requests catches OSError (the base of RequestException) around urllib3's
    # adapter call and wraps our budget exception as a ConnectionError argument.
    if isinstance(exc, RequestsConnectionError) and exc.args and isinstance(exc.args[0], RetryDelayExceeded):
        return exc.args[0].retry_at
    if not isinstance(exc, HTTPError) or exc.response is None:
        return None
    response = exc.response
    if response.status_code != 429 and response.status_code < 500:
        return None
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        delay = Retry().parse_retry_after(header)
    except RetryHeaderError:
        return None
    except ValueError:
        return None
    return time.monotonic() + delay if delay > 0 else None
