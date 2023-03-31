from typing import Callable

import requests

from withsecure.client.auth import OAuthAuthentication


class ApiClient(requests.Session):
    def __init__(self, client_id: str, secret: str, scope: str, log_cb: Callable[[str, str], None]):
        super().__init__()
        self.auth = OAuthAuthentication(
            client_id=client_id,
            secret=secret,
            grant_type="client_credentials",
            scope=scope,
            log_cb=log_cb,
        )
