import requests
from pyrate_limiter import Duration, Limiter, RequestRate
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(
            base_url="https://login.windows.net",
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )

        # This API has a throttling limit of 100 requests per 5 minutes
        # https://learn.microsoft.com/en-us/graph/api/messagetracingroot-list-messagetraces?view=graph-rest-1.0
        limiter = Limiter(RequestRate(limit=100, interval=Duration.MINUTE * 5))

        self.mount(
            "https://",
            LimiterAdapter(
                limiter=limiter,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
