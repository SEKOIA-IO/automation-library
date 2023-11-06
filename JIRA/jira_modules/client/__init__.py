import requests
from requests.auth import HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter

from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        email: str,
        api_key: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 10,
    ):
        super().__init__()
        self.auth = HTTPBasicAuth(username=email, password=api_key)
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
