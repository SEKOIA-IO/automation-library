from collections.abc import Generator, Mapping
from typing import Any, Self
from urllib.parse import parse_qs, quote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

TIMEOUT = 60
PAGE_SIZE = 100


class EasyVistaError(Exception):
    pass


def response_error(response: requests.Response) -> str | None:
    """
    Return the error of an answer, None on success.

    EasyVista reports business errors with a non-standard 590 status, and its JSON `error` field holds the reason.
    """
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and "error" in payload:
        return f"HTTP {response.status_code}: {payload['error']}"
    if not response.ok:
        return f"HTTP {response.status_code}: {response.text[:500]}"
    return None


class ApiClient(requests.Session):
    """
    HTTP session for the EasyVista Service Manager REST API: `https://{server}/api/v1/{tenant_id}/`.
    Authenticates with an access token (Bearer) or a login/password (Basic) and retries transient errors.
    """

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        use_token: bool = True,
        verify_ssl: bool = True,
        nb_retries: int = 3,
    ) -> None:
        super().__init__()
        self.api_url = f"{base_url.rstrip('/')}/api/v1/{quote(tenant_id.strip(), safe='')}"
        self.verify = verify_ssl
        self.headers["Accept"] = "application/json"
        if use_token:
            if not token:
                raise EasyVistaError("`token` is required when `use_token` is true")
            self.headers["Authorization"] = f"Bearer {token}"
        else:
            if not username or not password:
                raise EasyVistaError("`username` and `password` are required when `use_token` is false")
            self.auth = (username, password)

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[502, 503, 504],
                allowed_methods=["GET"],
                # Return the last answer once retries are exhausted, so callers see its HTTP status
                raise_on_status=False,
            )
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    @classmethod
    def from_configuration(cls, configuration: Mapping[str, Any], nb_retries: int = 3) -> Self:
        return cls(
            base_url=configuration["base_url"],
            tenant_id=configuration["tenant_id"],
            token=configuration.get("token"),
            username=configuration.get("username"),
            password=configuration.get("password"),
            use_token=configuration.get("use_token", True),
            verify_ssl=configuration.get("verify_ssl", True),
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
            if error := response_error(response):
                raise EasyVistaError(f"EasyVista answered {error} on GET /{resource}")
            payload = response.json()
            yield payload.get("records") or []

            next_offset = parse_qs(urlparse(payload.get("@next") or "").query).get("offset")
            if not next_offset or next_offset[0] == params.get("offset"):
                return
            params["offset"] = next_offset[0]
