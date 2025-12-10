import random
import time
import httpx
from httpx import Response
from httpx_ratelimiter import LimiterTransport

from .auth import ApiKeyAuthentication, UbikaCloudProtectorNextGenAuthentication


class ApiClient(httpx.Client):
    def __init__(
        self,
        token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ) -> None:
        super().__init__(
            http2=True,
            auth=ApiKeyAuthentication(token),
            transport=LimiterTransport(
                per_minute=ratelimit_per_minute,
            ),
            timeout=300.0,
        )
        self._nb_retries = nb_retries

    def request(self, method: str, url: str, **kwargs) -> Response | None:
        """Override request to add retry logic with exponential backoff."""
        response = None
        for attempt in range(self._nb_retries):
            try:
                response = super().request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt == self._nb_retries - 1:
                    raise e
                backoff_time = (2**attempt) * 1
                time.sleep(backoff_time)

        return response


class UbikaCloudProtectorNextGenApiClient(httpx.Client):
    def __init__(
        self,
        refresh_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ) -> None:
        super().__init__(
            http2=True,
            auth=UbikaCloudProtectorNextGenAuthentication(
                refresh_token=refresh_token, ratelimit_per_minute=ratelimit_per_minute
            ),
            timeout=300.0,
        )
        self._nb_retries = nb_retries
        self._status_forcelist = [500, 502, 503, 504]

    def request(self, method: str, url: str, **kwargs) -> Response | None:
        """Override request to add retry logic with jitter and specific status codes."""
        if method.upper() not in ["GET", "POST"]:
            return super().request(method, url, **kwargs)

        response = None
        for attempt in range(self._nb_retries):
            try:
                response = super().request(method, url, **kwargs)

                if response.status_code not in self._status_forcelist:
                    return response

                if attempt == self._nb_retries - 1:
                    return response

            except httpx.RequestError as e:
                if attempt == self._nb_retries - 1:
                    raise

            backoff_time = (2**attempt) * 2
            jitter = random.uniform(0, backoff_time * 0.1)
            time.sleep(backoff_time + jitter)

        return response
