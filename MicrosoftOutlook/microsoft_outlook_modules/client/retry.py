import time

from urllib3.response import HTTPResponse
from urllib3.util.retry import Retry as BaseRetry


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
            return self.parse_retry_after(retry_after)

        return None
