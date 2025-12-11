from functools import cached_property

import httpx
from tenacity import (
    Retrying,
    TryAgain,
    wait_random,
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

    @cached_property
    def retrying(self):
        wait_strategy = wait_exponential(multiplier=self.backoff_factor, max=self.backoff_max)

        if self.use_jitter:
            wait_strategy = wait_strategy + wait_random(0, 1)

        return Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_strategy,
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response | None:
        """
        Handle the request with retry logic.
        """
        for attempt in self.retrying:
            with attempt:
                response = self.transport.handle_request(request)

                if self.retry_on_status(response) and attempt.retry_state.attempt_number < self.max_retries:
                    raise TryAgain(response)

                return response
