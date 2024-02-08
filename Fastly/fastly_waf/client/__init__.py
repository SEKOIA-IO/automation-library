import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        email: str,
        token: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 100,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(email=email, token=token)
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
