import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import AuthBase, HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter


class ApiClient(requests.Session):
    def __init__(self, auth: AuthBase, ratelimit_per_second: int = 10, nb_retries: int = 5):
        super().__init__()
        self.auth = auth
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
