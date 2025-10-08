import requests
from requests_ratelimiter import LimiterAdapter
from urllib3.util import Retry
from requests.auth import HTTPBasicAuth


class ApiClient(requests.Session):
    def __init__(
        self,
        account_name: str,
        account_password: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 20,
    ):
        super().__init__()
        self.auth = HTTPBasicAuth(account_name, account_password)
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
