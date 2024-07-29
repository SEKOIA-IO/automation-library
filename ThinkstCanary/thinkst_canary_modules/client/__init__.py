import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ThinksCanaryAuth


class ApiClient(requests.Session):
    def __init__(self, base_url: str, auth_token: str, nb_retries: int = 5, ratelimit_per_second: int = 10):
        super().__init__()

        if not base_url.startswith("http"):
            base_url = "https://%s" % base_url

        self.base_url = base_url
        self.auth = ThinksCanaryAuth(auth_token=auth_token)

        adapter = LimiterAdapter(
            per_second=ratelimit_per_second,
            max_retries=Retry(total=nb_retries, backoff_factor=1),
        )

        self.mount("http://", adapter)
        self.mount("https://", adapter)
