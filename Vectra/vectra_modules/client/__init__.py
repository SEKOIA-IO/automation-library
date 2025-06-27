import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import VectraApiAuthentication


class ApiClient(requests.Session):
    def __init__(
        self, base_url: str, client_id: str, client_secret: str, ratelimit_per_second: int = 4, nb_retries: int = 5
    ):
        super().__init__()
        self.auth = VectraApiAuthentication(base_url=base_url, client_id=client_id, client_secret=client_secret)
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
