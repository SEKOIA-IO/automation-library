import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        api_token: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 600,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(api_token)
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
