import requests
from threading import local
from pyrate_limiter import Duration, Limiter, RequestRate
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from .auth import ApiKeyAuthentication
from .retry import Retry


class ApiClient(requests.Session):
    auth: ApiKeyAuthentication

    def __init__(
        self,
        auth: ApiKeyAuthentication,
        limiter_batch: Limiter,
        limiter_default: Limiter,
        nb_retries: int = 5,
    ):
        super().__init__()
        self.auth = auth
        self.limiter_batch = limiter_batch
        self.limiter_default = limiter_default
        self._retry_observer_state = local()
        self.headers.update({"Accept-Encoding": "gzip,deflate"})

        self.mount(
            "https://api.services.mimecast.com/siem/v1/batch/events/cg",
            LimiterAdapter(
                limiter=self.limiter_batch,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                    retry_observer=self._notify_retry_observer,
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
                    retry_observer=self._notify_retry_observer,
                ),
            ),
        )

    def set_retry_observer(self, observer) -> None:
        self._retry_observer_state.observer = observer

    def clear_retry_observer(self) -> None:
        self._retry_observer_state.observer = None

    def _notify_retry_observer(self) -> None:
        observer = getattr(self._retry_observer_state, "observer", None)
        if callable(observer):
            observer()
