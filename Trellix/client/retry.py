from typing import Any

from aiohttp import ClientResponse
from aiohttp_retry import RetryOptionsBase


class RetryWithRateLimiter(RetryOptionsBase):
    """
    This retry option will pause the retry according to the Retry-After, if defined, when the limit was exhausted (status code: 429).
    Otherwise, it will call the underlying retry options
    """

    RETRY_AFTER_HEADER = "Retry-After"

    def __init__(self, retry_options: RetryOptionsBase):
        self._wrapped_retry_options = retry_options

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped_retry_options, name)

    def get_timeout(self, attempt: int, response: ClientResponse | None = None) -> float:
        """
        Return the time to wait before the next attempt

        Args:
            attempt: The number of attempts for the request
            response: The response of the previous attempt
        """
        # Call the underlying retry options if the response is not defined or if the response
        # is not a too many requests response (status code: 429)
        if response is None or response.status != 429 or self.RETRY_AFTER_HEADER not in response.headers:
            return self._wrapped_retry_options.get_timeout(attempt, response)

        # Return the pause specified in the Retry-After header
        return float(response.headers["Retry-After"])
