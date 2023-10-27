from threading import Event
from typing import Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from withsecure.client.auth import OAuthAuthentication


class ApiClient(requests.Session):
    def __init__(self, client_id: str, secret: str, scope: str, stop_event: Event, log_cb: Callable[[str, str], None]):
        super().__init__()
        self.auth = OAuthAuthentication(
            client_id=client_id,
            secret=secret,
            grant_type="client_credentials",
            scope=scope,
            stop_event=stop_event,
            log_cb=log_cb,
        )

        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.mount("http://", adapter)
        self.mount("https://", adapter)
