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
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
        default_headers: dict[str, str] | None = None,
    ):
        super().__init__()
        self.auth: ApiKeyAuthentication = ApiKeyAuthentication(hostname, login, password)
        self.auth.authenticate()

        if default_headers is not None:
            self.headers.update(default_headers)

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
