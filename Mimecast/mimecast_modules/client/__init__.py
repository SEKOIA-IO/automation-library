import requests
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(
            client_id=client_id,
            client_secret=client_secret,
            ratelimit_per_second=ratelimit_per_minute,
            nb_retries=nb_retries,
        )
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
