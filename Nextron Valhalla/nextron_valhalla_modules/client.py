import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

VALHALLA_BASE_URL = "https://valhalla.nextron-systems.com"


class ValhallaFeedError(RuntimeError):
    """Raised when the Valhalla feed response is an error or malformed."""


class ValhallaClient:
    def __init__(self, api_key: str, timeout: float = 60.0):
        self._base_url = VALHALLA_BASE_URL
        self._api_key = api_key
        self._timeout = timeout
        # A failed fetch skips the whole sync, so retry transient errors.
        # Unlike the Sekoia create (see ``SekoiaClient``), ``getsigma`` is a
        # read that only uses POST to carry the key in a form body: retrying
        # it can't create anything, so POST is allowed here.
        self._session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=2.0,  # 0s, 4s, 8s between retries; Retry-After is honoured
            allowed_methods=frozenset(["POST"]),
            raise_on_status=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    def get_sigma_feed(self) -> list[dict]:
        resp = self._session.post(
            f"{self._base_url}/api/v1/getsigma",
            data={"apikey": self._api_key, "format": "json"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ValhallaFeedError(f"Valhalla returned an unexpected body: {resp.text[:200]}")
        if payload.get("status") == "error":
            raise ValhallaFeedError(f"Valhalla error: {payload.get('message')}")
        rules = payload.get("rules")
        # A missing or malformed ``rules`` key must not look like an empty
        # feed: the disable pass would treat every synced rule as removed.
        if not isinstance(rules, list):
            raise ValhallaFeedError(f"Valhalla response has no 'rules' list (keys: {sorted(payload)})")
        return rules
