import random
import time
import httpx
from httpx import Response
from httpx_ratelimiter import LimiterTransport

from .auth import ApiKeyAuthentication, UbikaCloudProtectorNextGenAuthentication
from .retry import ExponentialBackoffTransport


class ApiClient(httpx.Client):
    def __init__(
        self,
        token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
        use_jitter: bool = False,
    ) -> None:

        base_transport = httpx.HTTPTransport()

        retry_transport = ExponentialBackoffTransport(
            transport=base_transport,
            max_retries=nb_retries,
            backoff_factor=1.0,
            backoff_max=60.0,
            statuses={500, 502, 503, 504},
            use_jitter=use_jitter,
        )

        rate_limited_transport = LimiterTransport(
            transport=retry_transport,
            per_minute=ratelimit_per_minute,
        )

        super().__init__(
            http2=True,
            auth=ApiKeyAuthentication(token),
            timeout=300.0,
            transport=rate_limited_transport,
        )


class UbikaCloudProtectorNextGenApiClient(httpx.Client):
    def __init__(
        self,
        refresh_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
        use_jitter: bool = True,
    ) -> None:

        ubika_auth = UbikaCloudProtectorNextGenAuthentication(
            refresh_token=refresh_token, ratelimit_per_minute=ratelimit_per_minute
        )

        base_transport = httpx.HTTPTransport()

        retry_transport = ExponentialBackoffTransport(
            transport=base_transport,
            max_retries=nb_retries,
            backoff_factor=1.0,
            backoff_max=60.0,
            statuses={500, 502, 503, 504},
            use_jitter=use_jitter,
        )

        rate_limited_transport = LimiterTransport(
            transport=retry_transport,
            per_minute=ratelimit_per_minute,
        )

        super().__init__(
            http2=True,
            auth=ubika_auth,
            timeout=300.0,
            transport=rate_limited_transport,
        )
