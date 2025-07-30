
import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry
from .auth import BitdefenderApiAuth


class ApiClient(requests.Session):
    def __init__(self, instance_url: str, api_key: str, nb_retries: int = 5, ratelimit_per_second: int = 10):
        super().__init__()

        self.instance_url = instance_url
        self.api_key = api_key

        self.auth = BitdefenderApiAuth(api_key)
        self.mount('https://', LimiterAdapter(
            per_second=ratelimit_per_second,
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                ),
            ),
        )
