import requests
from requests_ratelimiter import LimiterAdapter
from requests.adapters import Retry

from cortex_module.client.auth import CortexAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        api_key: str,
        api_key_id: str,
        nb_retries: int = 5,
        ratelimit_per_seconde: int = 10,
    ):
        super().__init__()

        self.auth = CortexAuthentication(api_key, api_key_id)
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_seconde,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
