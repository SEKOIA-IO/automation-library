import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from .auth import HolmSecurityApiAuthentication


class ApiClient(requests.Session):
    """HTTP session preconfigured for the Holm Security API.

    Handles bearer-token authentication and retries on transient errors.
    """

    def __init__(self, base_url: str, token: str, nb_retries: int = 5):
        super().__init__()

        self.base_url = base_url.rstrip("/")
        self.auth = HolmSecurityApiAuthentication(token=token)
        self.headers.update({"Accept": "application/json"})

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
            )
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)
