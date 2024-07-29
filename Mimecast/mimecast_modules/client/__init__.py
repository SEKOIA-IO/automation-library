import requests
from pyrate_limiter import Duration, Limiter, RequestRate
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        nb_retries: int = 5,
        ratelimit_per_minute: int = 20,
    ):
        super().__init__()
        self.auth = ApiKeyAuthentication(
            client_id=client_id,
            client_secret=client_secret,
            ratelimit_per_second=ratelimit_per_minute,
            nb_retries=nb_retries,
        )

        # 50 times within a 15 minutes fixed window
        fifteen_minutes_rate = RequestRate(limit=50, interval=Duration.MINUTE * 15)
        self.mount(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            LimiterAdapter(
                limiter=Limiter(fifteen_minutes_rate),
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

        # 300 api calls/hour
        self.mount(
            "https://api.services.mimecast.com/siem/v1/events/cg",
            LimiterAdapter(
                per_hour=300,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
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
