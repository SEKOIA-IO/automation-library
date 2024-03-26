import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        auth_url: str,
        client_id: str,
        client_secret: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 20,
    ) -> None:
        super().__init__()
        self.auth: ApiKeyAuthentication = ApiKeyAuthentication(auth_url, client_id, client_secret)

        rate_limiter = LimiterAdapter(
            per_second=ratelimit_per_second,
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
            ),
        )

        self.mount("http://", rate_limiter)
        self.mount("https://", rate_limiter)
