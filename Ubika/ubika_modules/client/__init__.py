import httpx
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

        rate_limited_transport = LimiterTransport(
            transport=base_transport,
            per_minute=ratelimit_per_minute,
        )

        retry_transport = ExponentialBackoffTransport(
            transport=rate_limited_transport,
            max_retries=nb_retries,
            backoff_factor=1.0,
            backoff_max=60.0,
            statuses={500, 502, 503, 504},
            use_jitter=use_jitter,
        )

        super().__init__(
            http2=True,
            auth=ApiKeyAuthentication(token),
            timeout=300.0,
            transport=retry_transport,
        )


class UbikaCloudProtectorNextGenApiClient(httpx.Client):
    def __init__(
        self,
        refresh_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
        use_jitter: bool = True,
    ) -> None:
        base_transport = httpx.HTTPTransport()

        rate_limited_transport = LimiterTransport(
            transport=base_transport,
            per_minute=ratelimit_per_minute,
        )

        retry_transport = ExponentialBackoffTransport(
            transport=rate_limited_transport,
            max_retries=nb_retries,
            backoff_factor=1.0,
            backoff_max=60.0,
            network_wait=600,
            statuses={500, 502, 503, 504},
            use_jitter=use_jitter,
        )

        self._ubika_auth = UbikaCloudProtectorNextGenAuthentication(
            refresh_token=refresh_token, transport=retry_transport
        )

        super().__init__(
            http2=True,
            auth=self._ubika_auth,
            timeout=300.0,
            transport=retry_transport,
        )

    def close(self) -> None:
        self._ubika_auth.close()
        super().close()
