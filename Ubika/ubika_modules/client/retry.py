import random
import time
from functools import cached_property
from typing import final

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class ExponentialBackoffTransport(httpx.BaseTransport):

    def __init__(
        self,
        transport: httpx.BaseTransport,
        max_retries: int = 5,
        backoff_factor: float = 1.0,
        backoff_max: float = 60.0,
        statuses: set[int] | None = None,
        use_jitter: bool = False,
    ):
        super().__init__()
        self.transport = transport
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.backoff_max = backoff_max
        self.statuses = statuses or {408, 413, 429, 500, 502, 503, 504}
        self.use_jitter = use_jitter

    def retry_on_status(self, response: httpx.Response) -> bool:
        """
        Check if the response status code is in the set of retryable statuses.
        """
        return response.status_code in self.statuses

    def calculate_backoff(self, attempt_number: int) -> float:
        """
        Calculate backoff time with optional jitter.
        """
        backoff = (2**attempt_number) * self.backoff_factor
        if self.use_jitter:
            backoff = backoff * (0.5 + random.random() * 0.5)  # Add jitter (50-100% of backoff)
        return min(backoff, self.backoff_max)

    @cached_property
    def retrying(self):
        return Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff_factor, max=self.backoff_max),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """
        Handle the request with retry logic.
        """
        final_response = None
        for attempt in range(self.max_retries):
            try:
                response = self.transport.handle_request(request)

                if not self.retry_on_status(response) or attempt == self.max_retries - 1:
                    final_response = response
                    break

                # Calculate backoff and sleep
                backoff_time = self.calculate_backoff(attempt)
                time.sleep(backoff_time)

            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise httpx.RequestError(f"Request failed after {self.max_retries} attempts: {e}")
                backoff_time = self.calculate_backoff(attempt)
                time.sleep(backoff_time)

        if final_response is None:
            raise httpx.RequestError(f"Request failed after {self.max_retries} attempts.")

        return final_response
