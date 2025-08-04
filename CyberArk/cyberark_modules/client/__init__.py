import requests
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        auth: AuthBase,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 50,
        default_headers: dict[str, str] | None = None,
    ):
        super().__init__()
        self.auth = auth
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

        if default_headers:
            self.headers.update(default_headers)
