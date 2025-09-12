import requests
from requests.adapters import Retry
from requests.auth import HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter


class ApiClient(requests.Session):
    def __init__(self, apikey: str, nb_retries: int = 5, per_minute: int = 5):
        super().__init__()
        self.auth = HTTPBasicAuth("api", apikey)

        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=per_minute,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
