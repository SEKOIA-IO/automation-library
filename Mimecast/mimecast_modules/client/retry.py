import time
from typing import Callable

from urllib3.response import BaseHTTPResponse
from urllib3.util import Retry as BaseRetry


class Retry(BaseRetry):
    def __init__(self, *args, retry_observer: Callable[[], None] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_observer = retry_observer

    def new(self, **kw):
        retry = super().new(**kw)
        retry.retry_observer = self.retry_observer
        return retry

    def increment(self, *args, **kwargs):
        observer = getattr(self, "retry_observer", None)
        if callable(observer):
            observer()

        return super().increment(*args, **kwargs)

    @staticmethod
    def parse_ratelimit_retry_after(ratelimit_retry_after: str) -> float | None:
        """
        Parse the timestamp and return the delay before the next retry
        """
        lower_bound = float(ratelimit_retry_after)

        delay = lower_bound - time.time()
        if delay > 0:
            return delay

        return None

    def get_retry_after(self, response: BaseHTTPResponse) -> float | None:
        """
        Manage Rate-limiting headers from the server.
        """
        ratelimit_retry_after = response.headers.get("X-RateLimit-Reset")
        if ratelimit_retry_after:
            return self.parse_ratelimit_retry_after(ratelimit_retry_after)

        return None
