import requests
from requests.auth import HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        api_id: str,
        api_key: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 20,
    ):
        super().__init__()
        self.auth = HTTPBasicAuth(username=api_id, password=api_key)
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
