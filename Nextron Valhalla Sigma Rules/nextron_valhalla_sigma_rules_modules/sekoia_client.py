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
    """Raised when Sekoia reports the target rule UUID as missing from its
    catalog. Triggered by HTTP 404, or by HTTP 403 where the response body
    carries Sekoia's ``code: "AU202"`` — the documented marker for "rule
    existed but is gone". Any other 403 (plain permission problem, scope
    mismatch, key rotated across workspaces) now surfaces as a generic
    ``SekoiaAPIError`` instead of being mistaken for a deleted rule."""


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
        # timeouts, dropped connections) on idempotent methods. POST is
        # deliberately excluded: a read timeout after Sekoia already
        # created the rule would otherwise cause urllib3 to re-POST and
        # create a duplicate whose uuid we never see. HTTP 4xx/5xx
        # responses are also NOT retried — the caller interprets
        # 404/403-AU202 as "stale UUID, POST as new" and any other
        # status should surface immediately.
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=0,
            backoff_factor=1.0,  # 1s, 2s between retries
            allowed_methods=frozenset(["GET", "PUT"]),
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

    @staticmethod
    def _maybe_raise_not_found(
        resp: requests.Response, method: str, url: str
    ) -> None:
        """Raise ``SekoiaRuleNotFoundError`` when the response unambiguously
        means "the rule UUID is not in Sekoia's catalog".

        That is HTTP 404, or HTTP 403 with Sekoia error code ``AU202``.
        Other 403 responses (permission problem, workspace mismatch) are
        left for ``_ensure_ok`` to raise as a generic ``SekoiaAPIError`` —
        the trigger must not misread them as "stale uuid, re-POST".
        """
        if resp.status_code == 404:
            raise SekoiaRuleNotFoundError(
                f"{method} {url} returned HTTP 404: {resp.text[:500]}",
                status_code=404,
            )
        if resp.status_code == 403:
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            code = payload.get("code") if isinstance(payload, dict) else None
            if code == "AU202":
                raise SekoiaRuleNotFoundError(
                    f"{method} {url} returned HTTP 403 AU202: {resp.text[:500]}",
                    status_code=403,
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

    def get_rule(self, sekoia_uuid: str) -> dict:
        """Fetch a rule's current server-side state.

        Used by the sync trigger to read back the rule's current
        ``enabled`` flag before PUTting an update, so a user who flipped
        a rule off in the catalog isn't re-enabled on the next sync.
        """
        url = f"{self._base_url}/v1/sic/conf/rules-catalog/rules/{sekoia_uuid}"
        resp = self._session.get(url, timeout=self._timeout)
        self._maybe_raise_not_found(resp, "GET", url)
        self._ensure_ok(resp, "GET", url)
        try:
            return resp.json()
        except ValueError as exc:
            raise SekoiaAPIError(
                f"GET {url} returned non-JSON body: {resp.text[:500]}"
            ) from exc

    def update_rule(self, sekoia_uuid: str, body: dict) -> None:
        url = f"{self._base_url}/v1/sic/conf/rules-catalog/rules/{sekoia_uuid}"
        resp = self._session.put(url, json=body, timeout=self._timeout)
        self._maybe_raise_not_found(resp, "PUT", url)
        self._ensure_ok(resp, "PUT", url)
