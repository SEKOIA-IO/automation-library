import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ApiKeyAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        access_id: str,
        access_secret: str,
        audience: str | None = None,
        nb_retries: int = 5,
        # https://www.watchguard.com/help/docs/API/Content/en-US/api_get_started/api_limits.html
        rate_limit_per_second: int = 500,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(
            base_url=base_url,
            api_key=api_key,
            access_id=access_id,
            access_secret=access_secret,
            audience=audience,
            ratelimit_per_second=rate_limit_per_second,
            nb_retries=nb_retries,
        )
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=rate_limit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
