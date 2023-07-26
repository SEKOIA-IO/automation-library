import time
from typing import Callable

import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        hostname: str,
        login: str,
        password: str,
        log_callback: Callable,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ):
        super().__init__()
        self.auth: ApiKeyAuthentication = ApiKeyAuthentication(hostname, login, password, log_callback=log_callback)
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
