from collections.abc import Generator, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from sekoia_automation.asset_connector.utils import parse_retry_after
from sekoia_automation.exceptions import AssetConnectorRateLimitError
from urllib3 import Retry

from rapid7_insightvm.asset_connector.models import Rapid7Link, Rapid7PageMetadata


@dataclass
class AssetPage:
    """A page of ``POST /assets``, with the page number and cursor it was requested with."""

    data: list[Any]
    number: int
    cursor: str | None
    metadata: Rapid7PageMetadata


class ApiClient(requests.Session):

    ASSETS_ENDPOINT: str = "/assets"
    VULNERABILITIES_ENDPOINT: str = "/vulnerabilities"
    SORT: str = "id,ASC"

    # (connect, read) timeouts in seconds: delta queries on large asset pages can be slow.
    TIMEOUT: tuple[int, int] = (10, 120)
    # Pause applied when the rate limit persists after the retries, capped to MAX_RATE_LIMIT_WAIT.
    DEFAULT_RATE_LIMIT_WAIT: float = 300.0
    MAX_RATE_LIMIT_WAIT: float = 3600.0

    def __init__(self, region: str, api_key: str, nb_retries: int = 5):
        super().__init__()

        self.region = region.strip().lower()
        self.base_url = f"https://{self.region}.api.insight.rapid7.com/vm/v4/integration"
        self.verify = True
        self.headers.update(
            {
                "X-Api-Key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip",
            }
        )

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=nb_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset({"GET", "POST"}),
                respect_retry_after_header=False,
                # Return the last response once the retries are exhausted, so its status is readable.
                raise_on_status=False,
            )
        )
        self.mount("https://", adapter)

    @classmethod
    def from_configuration(cls, configuration: Any) -> "ApiClient":
        """Build the client from the module configuration (``region``, ``api_key``)."""
        if not isinstance(configuration, Mapping):
            raise TypeError(f"Expected the module configuration as a mapping, got {type(configuration).__name__}")
        return cls(region=str(configuration["region"]), api_key=str(configuration["api_key"]))

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    @classmethod
    def raise_for_status(cls, response: Response) -> None:
        if response.status_code == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"), cls.DEFAULT_RATE_LIMIT_WAIT)
            raise AssetConnectorRateLimitError(retry_after=min(retry_after, cls.MAX_RATE_LIMIT_WAIT))
        response.raise_for_status()

    @staticmethod
    def error_message(error: RequestException) -> str:
        """Append the ``message`` of the InsightVM error body to the error."""
        response = error.response
        if response is None:
            return str(error)
        try:
            body = response.json()
        except ValueError:
            return str(error)
        detail = body.get("message") if isinstance(body, dict) else None
        return f"{error} - {detail}" if detail else str(error)

    def _search(self, path: str, params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        response = self.post(self.url(path), params=params, json=body, timeout=self.TIMEOUT)
        self.raise_for_status(response)
        return response.json()

    @staticmethod
    def next_cursor(content: dict[str, Any]) -> tuple[bool, str | None]:
        """Whether a next page exists, and the cursor to request it with."""
        links = [Rapid7Link.model_validate(link) for link in content.get("links") or [] if isinstance(link, dict)]
        next_link = next((link for link in links if (link.rel or "").lower() == "next"), None)
        if next_link is None:
            return False, None
        metadata = Rapid7PageMetadata.model_validate(content.get("metadata") or {})
        if metadata.cursor:
            return True, metadata.cursor
        cursor = parse_qs(urlparse(next_link.href or "").query).get("cursor")
        return True, cursor[0] if cursor else None

    @staticmethod
    def id_filter(vuln_ids: list[str]) -> str:
        quoted = ", ".join("'" + vuln_id.replace("\\", "\\\\").replace("'", "\\'") + "'" for vuln_id in vuln_ids)
        return f"vulnerability.id IN [{quoted}]"

    def iter_asset_pages(
        self,
        current_time: str,
        comparison_time: str,
        page_size: int,
        page: int = 0,
        cursor: str | None = None,
    ) -> Generator[AssetPage, None, None]:
        """Walk the pages of ``POST /assets`` with the delta between the two times, from a page and cursor.

        ``same`` is always requested: with ``new`` and ``remediated`` it gives the state of every
        vulnerability at both times. Every page is requested with the same parameters plus the
        cursor of the previous one.
        """
        while True:
            params: dict[str, Any] = {
                "size": page_size,
                "sort": self.SORT,
                "currentTime": current_time,
                "comparisonTime": comparison_time,
                "includeSame": "true",
            }
            if page:
                params["page"] = page
            if cursor:
                params["cursor"] = cursor

            content = self._search(self.ASSETS_ENDPOINT, params, {})
            data = content.get("data") or []
            metadata = Rapid7PageMetadata.model_validate(content.get("metadata") or {})
            yield AssetPage(data=data, number=page, cursor=cursor, metadata=metadata)

            has_next, next_cursor = self.next_cursor(content)
            if not has_next:
                return
            if next_cursor is not None and next_cursor == cursor:
                raise RuntimeError(f"The asset pages do not advance: cursor {cursor!r} returned again")
            page, cursor = page + 1, next_cursor

    def search_vulnerabilities(self, vuln_ids: list[str]) -> Generator[Any, None, None]:
        """Yield the raw definitions of the given vulnerability ids, following the pages."""
        body = {"vulnerability": self.id_filter(vuln_ids)}
        params: dict[str, Any] = {"size": len(vuln_ids)}
        page = 0
        while True:
            content = self._search(self.VULNERABILITIES_ENDPOINT, params, body)
            data = content.get("data") or []
            yield from data

            has_next, next_cursor = self.next_cursor(content)
            if not has_next:
                return
            if next_cursor is not None and next_cursor == params.get("cursor"):
                raise RuntimeError(f"The vulnerability pages do not advance: cursor {next_cursor!r} returned again")
            cursor = next_cursor
            page += 1
            params = {"size": len(vuln_ids), "page": page}
            if cursor:
                params["cursor"] = cursor
