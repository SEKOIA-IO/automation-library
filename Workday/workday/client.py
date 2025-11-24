import requests
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

class WorkdayApiClient:
    """Workday OAuth2 client with refresh token support"""

    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        workday_host: str,
        timeout: int = 30,
    ):
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.workday_host = workday_host
        self.timeout = timeout

        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._token_lock = Lock()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _is_token_valid(self) -> bool:
        return self._access_token and self._token_expiry and self._token_expiry > self._now()

    def _request_new_token(self) -> None:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(self.token_endpoint, data=payload, headers=headers, timeout=self.timeout)
        if resp.status_code == 401:
            raise PermissionError(f"Authentication failed: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = self._now() + timedelta(seconds=expires_in - 30)

    def get_access_token(self) -> str:
        with self._token_lock:
            if not self._is_token_valid():
                self._request_new_token()
            return self._access_token  # type: ignore

    def _make_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_access_token()}", "Accept": "application/json"}

    def get(self, url: str, params: dict = None, **kwargs):
        headers = kwargs.pop("headers", {})
        headers.update(self._make_headers())
        return requests.get(url, params=params, headers=headers, timeout=self.timeout, **kwargs)
