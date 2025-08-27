import requests
from requests_ratelimiter import LimiterAdapter
from urllib3 import Retry

from .auth import ZscalerZIAAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        cloud_name: str,
        username: str,
        password: str,
        api_key: str,
        nb_retries: int = 5,
        ratelimit_per_second: int = 10,
        default_headers: dict[str, str] | None = None,
    ):
        super().__init__()
        self.auth: ZscalerZIAAuthentication = ZscalerZIAAuthentication(
            cloud_name=cloud_name,
            username=username,
            password=password,
            api_key=api_key,
            ratelimit_per_second=ratelimit_per_second,
        )
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

        if default_headers:
            self.headers.update(default_headers)

    @property
    def base_url(self) -> str:
        return self.auth.base_url
