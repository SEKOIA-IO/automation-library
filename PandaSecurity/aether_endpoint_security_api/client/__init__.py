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
        ratelimit_per_minute: int = 20,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(
            base_url=base_url,
            api_key=api_key,
            access_id=access_id,
            access_secret=access_secret,
            audience=audience,
            ratelimit_per_minute=ratelimit_per_minute,
            nb_retries=nb_retries,
        )
        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=ratelimit_per_minute,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
