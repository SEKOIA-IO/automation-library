import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import LookoutApiAuthentication


class ApiClient(requests.Session):
    def __init__(self, base_url: str, api_token: str, ratelimit_per_minute: int = 20, nb_retries: int = 5):
        super().__init__()
        self.auth = LookoutApiAuthentication(base_url=base_url, api_token=api_token)
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

    def get_sse_stream(self, url: str, params: dict | None = None) -> requests.Response:
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        return self.get(url, stream=True, headers=headers, params=params)
