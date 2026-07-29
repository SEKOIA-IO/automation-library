from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SekoiaAPIError(RuntimeError):
    """Raised when the Sekoia API returns a non-2xx response or an unexpected body."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SekoiaRuleNotFoundError(SekoiaAPIError):
    """Raised on PUT to a rule UUID that Sekoia doesn't own for this API
    key. Sekoia returns HTTP 403 (code AU202) for UUIDs that were
    previously created by this key but have since been deleted, so we
    treat 403 and 404 on ``update_rule`` interchangeably as "stale
    identifier — POST it as new instead"."""


class SekoiaClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        # One HTTP session across all requests — reuses the TCP + TLS
        # handshake for the ~thousands of rule PUTs a full sync makes.
        # Without pooling the trigger opens a fresh connection per rule
        # and Sekoia's edge intermittently connect-times-out under that
        # rate of new inbound connections from a single source IP.
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        # Retry only transient transport-layer errors (connect/read
        # timeouts, dropped connections). HTTP 4xx/5xx responses are
        # deliberately NOT retried — the caller interprets 403/404 as
        # "stale UUID, POST as new" and any other status should surface
        # immediately to the sync trigger's per-rule failure counter.
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=0,
            backoff_factor=1.0,  # 1s, 2s between retries
            allowed_methods=frozenset(["GET", "POST", "PUT"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    @staticmethod
    def _ensure_ok(resp: requests.Response, method: str, url: str) -> None:
        if resp.ok:
            return
        body = resp.text[:500]
        raise SekoiaAPIError(
            f"{method} {url} returned HTTP {resp.status_code}: {body}",
            status_code=resp.status_code,
        )

    def create_rule(self, body: dict) -> str:
        url = f"{self._base_url}/v1/sic/conf/rules-catalog/rules"
        resp = self._session.post(url, json=body, timeout=self._timeout)
        self._ensure_ok(resp, "POST", url)
        try:
            data = resp.json()
        except ValueError as exc:
            raise SekoiaAPIError(
                f"POST {url} returned non-JSON body: {resp.text[:500]}"
            ) from exc
        sekoia_uuid = data.get("uuid") or data.get("id")
        if not sekoia_uuid:
            raise SekoiaAPIError(
                f"POST {url} succeeded but response had no uuid/id field. "
                f"Body: {resp.text[:500]}"
            )
        return sekoia_uuid

    def update_rule(self, sekoia_uuid: str, body: dict) -> None:
        url = f"{self._base_url}/v1/sic/conf/rules-catalog/rules/{sekoia_uuid}"
        resp = self._session.put(url, json=body, timeout=self._timeout)
        if resp.status_code in (403, 404):
            raise SekoiaRuleNotFoundError(
                f"PUT {url} returned HTTP {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
            )
        self._ensure_ok(resp, "PUT", url)
