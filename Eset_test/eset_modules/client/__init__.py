import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import EsetProtectApiAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        auth_base_url: str,
        username: str,
        password: str,
        ratelimit_per_second: int = 10,
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = EsetProtectApiAuthentication(
            auth_base_url=auth_base_url,
            username=username,
            password=password,
            ratelimit_per_second=ratelimit_per_second,
        )
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
