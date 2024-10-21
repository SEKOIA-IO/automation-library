import requests
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        tenant_id: str,
        base_url: str = "https://api.securitycenter.microsoft.com",
        nb_retries: int = 5,
        ratelimit_per_minute: int = 45,
    ):
        super().__init__()
        self.base_url = base_url
        self.auth = ApiKeyAuthentication(
            app_id=app_id, app_secret=app_secret, tenant_id=tenant_id, ratelimit_per_minute=ratelimit_per_minute
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
