import requests
from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry

from hornetsecurity_modules.client.auth import ApiTokenAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        api_token: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 20,
    ):
        super().__init__()
        self.auth = ApiTokenAuthentication(api_token)
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
