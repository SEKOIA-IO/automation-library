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


class UbikaCloudProtectorNextGenApiClient(requests.Session):
    def __init__(
        self,
        refresh_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ) -> None:
        super().__init__()
        self.auth = UbikaCloudProtectorNextGenAuthentication(refresh_token=refresh_token)
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
