import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import HarfangLabApiAuthentication


class ApiClient(requests.Session):
    def __init__(self, instance_url: str, token: str, nb_retries: int = 5, ratelimit_per_second: int = 100):
        super().__init__()

        self.instance_url = instance_url
        self.token = token

        self.auth = HarfangLabApiAuthentication(token=token)
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
