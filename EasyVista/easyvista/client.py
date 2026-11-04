from collections.abc import Generator, Mapping
from typing import Any, Self
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

TIMEOUT = 60
PAGE_SIZE = 100


class ApiClient(requests.Session):
    """
    HTTP session for the EasyVista Service Manager REST API: `https://{server}/api/v1/{account}/`.
    Authenticates with an access token and retries transient errors.
    """

    def __init__(self, base_url: str, account: str, token: str, nb_retries: int = 5) -> None:
        super().__init__()
        self.api_url = f"{base_url.rstrip('/')}/api/v1/{account.strip('/')}"
        self.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
                # Return the last answer once retries are exhausted, so callers see its HTTP status
                raise_on_status=False,
            )
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    @classmethod
    def from_configuration(cls, configuration: Mapping[str, Any], nb_retries: int = 5) -> Self:
        return cls(
            base_url=configuration["base_url"],
            account=configuration["account"],
            token=configuration["api_token"],
            nb_retries=nb_retries,
        )

    def list_records(self, resource: str, params: dict[str, Any]) -> Generator[list[dict[str, Any]]]:
        """
        Yield the records of a list endpoint, page by page.

        Pages are linked by `@next` (EV Service Manager 2024.3+). Its URL drops the `fields` and `search`
        parameters, so only its `offset` is reused with the original parameters.
        """
        params = {"max_rows": PAGE_SIZE, **params}
        while True:
            response = self.get(f"{self.api_url}/{resource}", params=params, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            yield payload.get("records") or []

            next_offset = parse_qs(urlparse(payload.get("@next") or "").query).get("offset")
            if not next_offset or next_offset[0] == params.get("offset"):
                return
            params["offset"] = next_offset[0]
