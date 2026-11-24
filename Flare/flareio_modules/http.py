from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# (connect, read) in seconds: a page usually answers in about 1 s
REQUEST_TIMEOUT = (10.0, 60.0)


class TimeoutHTTPAdapter(HTTPAdapter):
    """
    Gives a timeout to the calls that have none: the SDK sets none, so a call Flare never answers blocked the
    connector until the connection broke (16 minutes once). A timed out call is then retried like a 5xx.
    """

    def __init__(self, timeout: tuple[float, float], **kwargs: Any) -> None:
        self.timeout = timeout
        super().__init__(**kwargs)

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float | None, float | None] | None = None,
        verify: bool | str = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
    ) -> requests.Response:
        return super().send(request, stream, self.timeout if timeout is None else timeout, verify, cert, proxies)


def create_session() -> requests.Session:
    """
    Session for the Flare SDK's client. The SDK's own session retries 429, 502, 503 and 504 only, while Flare also
    answers intermittent 500s to both the search and the details: without a retry, each one fails the batch and costs
    a `frequency` wait in `run()`. Same retries as the SDK's otherwise, plus a timeout on every call.
    """
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        backoff_max=15,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"GET", "POST"},
    )
    session.mount("https://", TimeoutHTTPAdapter(timeout=REQUEST_TIMEOUT, max_retries=retry))
    return session
