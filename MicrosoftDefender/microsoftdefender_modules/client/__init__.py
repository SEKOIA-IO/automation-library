import requests
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication, GraphApiKeyAuthentication
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


class GraphApiClient(requests.Session):
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = GraphApiKeyAuthentication(
            base_url="https://login.windows.net",
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )

        # This API has a throttling limit of 150 requests per minute
        # https://learn.microsoft.com/en-us/graph/throttling-limits#security-detections-and-incidents-service-limits

        self.mount(
            "https://",
            LimiterAdapter(
                per_minute=150,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
