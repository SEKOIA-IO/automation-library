# workday/client/http_client.py
import aiohttp
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from aiolimiter import AsyncLimiter
from workday.client.errors import WorkdayError, WorkdayAuthError, WorkdayRateLimitError


class WorkdayClient:
    def __init__(
        self,
        workday_host: str,
        tenant_name: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_endpoint: Optional[str] = None,
    ):
        self.workday_host = workday_host
        self.tenant_name = tenant_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._explicit_token_endpoint = token_endpoint

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._rate_limiter = AsyncLimiter(max_rate=10, time_period=1)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def base_url(self) -> str:
        return f"https://{self.workday_host}/ccx/api/privacy/v1/{self.tenant_name}"

    @property
    def token_endpoint(self) -> str:
        if self._explicit_token_endpoint:
            return self._explicit_token_endpoint
        return f"https://{self.workday_host}/ccx/oauth2/{self.tenant_name}/token"

    async def _get_access_token(self) -> str:
        # FIXED: Add assertion to satisfy mypy that session is not None
        if self._session is None:
            raise WorkdayError("HTTP session not initialized")

        # return cached if valid
        if self._access_token and self._token_expires_at and datetime.now(timezone.utc) < self._token_expires_at:
            return self._access_token

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with self._rate_limiter:
            async with self._session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                raise_for_status=False,
            ) as resp:
                if resp.status == 401:
                    # invalid credentials: raise to stop connector
                    text = await resp.text()
                    raise WorkdayAuthError(f"Token exchange unauthorized: {text}")
                if resp.status != 200:
                    text = await resp.text()
                    raise WorkdayError(f"Token request failed ({resp.status}): {text}")
                token_data = await resp.json()

        self._access_token = token_data.get("access_token")
        expires_in = int(token_data.get("expires_in", 3600))
        # add safety buffer 300s
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
        return self._access_token

    async def fetch_activity_logs(
        self, from_time: datetime, to_time: datetime, limit: int = 1000, offset: int = 0
    ) -> List[Dict[str, Any]]:
        if not self._session:
            raise WorkdayError("HTTP session not initialized")

        url = f"{self.base_url}/activityLogging"
        # FIXED: Use Dict[str, str] for params to satisfy mypy
        params: Dict[str, str] = {
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "to": to_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "limit": str(limit),
            "offset": str(offset),
            "instancesReturned": "1",
        }

        headers = {"Accept": "application/json"}

        max_attempts = 3
        attempt = 0
        backoff_base = 2

        while attempt < max_attempts:
            attempt += 1
            # ensure token
            access_token = await self._get_access_token()
            headers["Authorization"] = f"Bearer {access_token}"

            async with self._rate_limiter:
                async with self._session.get(url, params=params, headers=headers, raise_for_status=False) as resp:
                    # 401: try refreshing once
                    if resp.status == 401:
                        # invalidate token and retry one time
                        self._access_token = None
                        self._token_expires_at = None
                        if attempt < max_attempts:
                            await sleep(0.5)  # small pause before retry
                            continue
                        raise WorkdayAuthError("Unauthorized when fetching activity logs")
                    if resp.status == 429:
                        ra = resp.headers.get("Retry-After")
                        wait = 60
                        if ra:
                            try:
                                wait = int(ra)
                            except Exception:
                                # keep default if malformed
                                pass
                        # exponential backoff with small jitter
                        wait = wait * (backoff_base ** (attempt - 1))
                        await sleep(wait)
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        raise WorkdayError(f"ActivityLogging request failed ({resp.status}): {text}")
                    return await resp.json()

        raise WorkdayRateLimitError("Exceeded maximum retry attempts while fetching activity logs")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        # Validate token immediately at __aenter__ to fail fast on bad credentials
        await self._get_access_token()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
