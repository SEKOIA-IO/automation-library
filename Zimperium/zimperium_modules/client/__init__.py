import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ZimperiumApiAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 600,
    ):
        super().__init__()
        self.auth = ZimperiumApiAuthentication(
            base_url=base_url, client_id=client_id, client_secret=client_secret
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
