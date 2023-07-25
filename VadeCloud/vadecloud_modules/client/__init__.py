import time

import requests
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        hostname: str,
        login: str,
        password: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ):
        super().__init__()
        self.auth: ApiKeyAuthentication = ApiKeyAuthentication(hostname, login, password)
        self.auth.authenticate()

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

    @property
    def account_id(self):
        return self.auth.account_id
