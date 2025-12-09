import random
import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication, UbikaCloudProtectorNextGenAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ) -> None:
        super().__init__()
        self.auth: ApiKeyAuthentication = ApiKeyAuthentication(token)
        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=ratelimit_per_minute,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )


class RetryWithJitter(Retry):
    """Custom Retry class that adds jitter to backoff time."""

    def get_backoff_time(self) -> float:
        backoff = super().get_backoff_time()
        jitter = random.uniform(0, backoff * 0.1)
        return backoff + jitter


class UbikaCloudProtectorNextGenApiClient(requests.Session):
    def __init__(
        self,
        refresh_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ) -> None:
        super().__init__()
        self.auth = UbikaCloudProtectorNextGenAuthentication(
            refresh_token=refresh_token, ratelimit_per_minute=ratelimit_per_minute
        )

        retry_strategy = RetryWithJitter(
            total=nb_retries,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )

        self.mount(
            "https://",
            LimiterAdapter(per_minute=ratelimit_per_minute, max_retries=retry_strategy),
        )
