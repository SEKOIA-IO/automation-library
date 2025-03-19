import requests
from pyrate_limiter import Duration, Limiter, RequestRate
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        auth: AuthBase,
        limiter_batch: Limiter,
        limiter_default: Limiter,
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = auth
        self.limiter_batch = limiter_batch
        self.limiter_default = limiter_default
        self.headers.update({"Accept-Encoding": "gzip,deflate"})

        self.mount(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            LimiterAdapter(
                limiter=self.limiter_batch,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

        self.mount(
            "https://",
            LimiterAdapter(
                limiter=self.limiter_default,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )
