import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import TrendMicroVisionAuth


class TrendMicroVisionOneApiClient(requests.Session):
    def __init__(self, api_key: str):
        super().__init__()
        self.auth = TrendMicroVisionAuth(api_key=api_key)

        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=600,
                per_hour=30_000,
                max_retries=Retry(
                    total=5,
                    backoff_factor=1,
                ),
            ),
        )
