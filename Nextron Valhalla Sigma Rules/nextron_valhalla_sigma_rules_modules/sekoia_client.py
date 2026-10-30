from collections.abc import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SekoiaAPIError(RuntimeError):
    """Raised when the Sekoia API returns a non-2xx response or an unexpected body."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SekoiaRuleNotFoundError(SekoiaAPIError):
    """Raised when Sekoia answers HTTP 404 for a rule UUID. 403 is never
    treated as "not found": the API documents it as "Insufficient
    permissions", and misreading it would make the sync re-create rules."""


LIST_PAGE_SIZE = 100
MAX_LIST_PAGES = 10_000  # safety bound against a server that ignores ``offset``

RULES_PATH = "/v1/sic/conf/rules-catalog/rules"
ALERT_TYPES_PATH = "/v1/sic/conf/alerts/types"
INTHREAT_OBJECTS_PATH = "/v2/inthreat/objects"

QueryParams = dict[str, str | int]


def rule_tag_names(rule: dict) -> set[str]:
    """Tag names of a catalog rule. Sekoia returns tags as
    ``[{"uuid": ..., "name": ...}, …]``; plain strings are accepted too."""
    names: set[str] = set()
    for tag in rule.get("tags") or []:
        if isinstance(tag, dict) and isinstance(tag.get("name"), str):
            names.add(tag["name"])
        elif isinstance(tag, str):
            names.add(tag)
    return names


class SekoiaClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        if not base_url.lower().startswith("https://"):
            # The bearer token goes in every request header; never send it
            # over plain HTTP.
            raise ValueError(f"sekoia_base_url must use https:// (got {base_url!r})")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        # One HTTP session across all requests — reuses the TCP + TLS
        # handshake for the ~thousands of rule PUTs a full sync makes.
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
        # Retry only transient transport-layer errors (connect/read
        # timeouts, dropped connections) on idempotent methods. POST is
        # deliberately excluded: a read timeout after Sekoia already
        # created the rule would otherwise cause urllib3 to re-POST and
        # create a duplicate whose uuid we never see. HTTP 4xx/5xx
        # responses are not retried.
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
    def _maybe_raise_not_found(resp: requests.Response, method: str, url: str) -> None:
        """Raise ``SekoiaRuleNotFoundError`` on HTTP 404 — the only status
        the API documents as "unknown rule"."""
        if resp.status_code == 404:
            raise SekoiaRuleNotFoundError(
                f"{method} {url} returned HTTP 404: {resp.text[:500]}",
                status_code=404,
            )

    @staticmethod
    def _json(resp: requests.Response, method: str, url: str):
        try:
            return resp.json()
        except ValueError as exc:
            raise SekoiaAPIError(f"{method} {url} returned non-JSON body: {resp.text[:500]}") from exc

    def _paginate(self, path: str, params: QueryParams, page_size: int) -> Iterator[dict]:
        """Walk a ``{items, total}`` list endpoint with ``limit``/``offset``.

        Any HTTP or shape error raises — callers that build state from the
        listing (the sync's catalog scan) must never continue on a partial
        result.
        """
        url = f"{self._base_url}{path}"
        offset = 0
        for _ in range(MAX_LIST_PAGES):
            page_params: QueryParams = {**params, "limit": page_size, "offset": offset}
            resp = self._session.get(url, params=page_params, timeout=self._timeout)
            self._ensure_ok(resp, "GET", url)
            data = self._json(resp, "GET", url)
            if not isinstance(data, dict):
                raise SekoiaAPIError(f"GET {url} returned unexpected list shape: {resp.text[:500]}")
            items = data.get("items")
            if items is None:
                items = data.get("data") or []
            if not isinstance(items, list):
                raise SekoiaAPIError(f"GET {url} returned unexpected list shape: {resp.text[:500]}")
            yield from items
            offset += len(items)
            total = data.get("total")
            if not items or (isinstance(total, int) and offset >= total):
                return
        raise SekoiaAPIError(f"GET {url} did not terminate after {MAX_LIST_PAGES} pages ({offset} items fetched).")

    def create_rule(self, body: dict) -> str:
        url = f"{self._base_url}{RULES_PATH}"
        resp = self._session.post(url, json=body, timeout=self._timeout)
        self._ensure_ok(resp, "POST", url)
        data = self._json(resp, "POST", url)
        sekoia_uuid = data.get("uuid") if isinstance(data, dict) else None
        if not sekoia_uuid:
            raise SekoiaAPIError(f"POST {url} succeeded but response had no uuid field. Body: {resp.text[:500]}")
        return sekoia_uuid

    def get_rule(self, sekoia_uuid: str) -> dict:
        """Fetch a rule's current server-side state."""
        url = f"{self._base_url}{RULES_PATH}/{sekoia_uuid}"
        resp = self._session.get(url, timeout=self._timeout)
        self._maybe_raise_not_found(resp, "GET", url)
        self._ensure_ok(resp, "GET", url)
        return self._json(resp, "GET", url)

    def update_rule(self, sekoia_uuid: str, body: dict) -> None:
        url = f"{self._base_url}{RULES_PATH}/{sekoia_uuid}"
        resp = self._session.put(url, json=body, timeout=self._timeout)
        self._maybe_raise_not_found(resp, "PUT", url)
        self._ensure_ok(resp, "PUT", url)

    def disable_rule(self, sekoia_uuid: str) -> None:
        """Disable one rule through the dedicated endpoint, which flips only
        ``enabled`` and leaves every other rule setting untouched."""
        url = f"{self._base_url}{RULES_PATH}/{sekoia_uuid}/disabled"
        resp = self._session.put(url, timeout=self._timeout)
        self._maybe_raise_not_found(resp, "PUT", url)
        self._ensure_ok(resp, "PUT", url)

    def iter_rules(
        self,
        tag_name: str | None = None,
        community_uuid: str | None = None,
        page_size: int = LIST_PAGE_SIZE,
    ) -> Iterator[dict]:
        """Paginate ``GET /v1/sic/conf/rules-catalog/rules`` and yield each
        rule dict.

        Filters are sent server-side (``match[tag_name]``,
        ``match[community_uuid]``) and re-applied
        client-side as a safety net, so a rule that doesn't match is never
        yielded even if the server ignores a filter.
        """
        params: QueryParams = {}
        if tag_name:
            params["match[tag_name]"] = tag_name
        if community_uuid:
            params["match[community_uuid]"] = community_uuid
        for item in self._paginate(RULES_PATH, params, page_size):
            if tag_name and tag_name not in rule_tag_names(item):
                continue
            if community_uuid and item.get("community_uuid") != community_uuid:
                continue
            yield item

    def list_alert_types(self, page_size: int = LIST_PAGE_SIZE) -> list[dict]:
        """All alert types visible to the key (``GET /v1/sic/conf/alerts/types``)."""
        return list(self._paginate(ALERT_TYPES_PATH, {}, page_size))

    def find_attack_pattern(self, external_id: str) -> str | None:
        """Return the STIX id (``attack-pattern--…``) of the ATT&CK technique
        with this external id (e.g. ``T1059``), or ``None`` if unknown."""
        url = f"{self._base_url}{INTHREAT_OBJECTS_PATH}"
        params: QueryParams = {"match[external_id]": external_id, "limit": 10}
        resp = self._session.get(url, params=params, timeout=self._timeout)
        self._ensure_ok(resp, "GET", url)
        data = self._json(resp, "GET", url)
        items = data.get("items") if isinstance(data, dict) else None
        for item in items or []:
            stix_id = item.get("id") if isinstance(item, dict) else None
            if isinstance(stix_id, str) and stix_id.startswith("attack-pattern--"):
                return stix_id
        return None
