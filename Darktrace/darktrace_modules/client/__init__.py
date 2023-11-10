import requests
from requests_ratelimiter import LimiterAdapter

from darktrace_modules.client.auth import ApiKeyAuthentication
from darktrace_modules.client.retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        public_key: str,
        private_key: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
        default_headers: dict[str, str] | None = None,
    ):
        super().__init__()

        if default_headers is not None:
            self.headers.update(default_headers)

        self.auth = ApiKeyAuthentication(public_key, private_key)
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
