import requests

VALHALLA_BASE_URL = "https://valhalla.nextron-systems.com"


class ValhallaFeedError(RuntimeError):
    """Raised when the Valhalla feed response is an error or malformed."""


class ValhallaClient:
    def __init__(self, api_key: str, timeout: float = 60.0):
        self._base_url = VALHALLA_BASE_URL
        self._api_key = api_key
        self._timeout = timeout

    def get_sigma_feed(self) -> list[dict]:
        resp = requests.post(
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
