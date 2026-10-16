from collections.abc import Mapping
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3 import Retry


class ApiClient(requests.Session):
    """HTTP session preconfigured for the InsightVM Security Console API v3.

    Authenticates with HTTP Basic (the account must not use two-factor authentication)
    and retries the transient errors, honouring ``Retry-After``. POST is retried too:
    the connectors only use it for ``/api/3/assets/search``, which is a read.
    """

    # (connect, read) timeouts in seconds: asset pages with the default `details` view are large.
    TIMEOUT: tuple[int, int] = (10, 120)

    def __init__(self, base_url: str, username: str, password: str, verify: bool = True, nb_retries: int = 5):
        super().__init__()

        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password)
        self.verify = verify
        self.headers.update({"Accept": "application/json", "Accept-Encoding": "gzip"})

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset({"GET", "POST"}),
                respect_retry_after_header=True,
            )
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    @classmethod
    def from_configuration(cls, configuration: Any) -> "ApiClient":
        """Build the client from the module configuration (``base_url``, ``username``, ``password``)."""
        if not isinstance(configuration, Mapping):
            raise TypeError(f"Expected the module configuration as a mapping, got {type(configuration).__name__}")
        return cls(
            base_url=str(configuration["base_url"]),
            username=configuration["username"],
            password=configuration["password"],
            verify=bool(configuration.get("verify_certificate", True)),
        )

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"
