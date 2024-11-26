import requests
from requests.adapters import HTTPAdapter, Retry
from requests.auth import HTTPBasicAuth
from requests_ratelimiter import LimiterAdapter

from .auth import TrendMicroVisionAuth


class ApiClient(requests.Session):
    def __init__(self, username: str, api_key: str, nb_retries: int = 5):
        super().__init__()
        self.auth = HTTPBasicAuth(username=username, password=api_key)
        self.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                )
            ),
        )


class TrendMicroVisionApiClient(requests.Session):
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
