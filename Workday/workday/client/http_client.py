# workday/client/http_client.py
import aiohttp
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
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
        # return cached if valid
        if self._access_token and self._token_expires_at and datetime.now(timezone.utc) < self._token_expires_at:
            return self._access_token

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        """
        This code performs an authenticated token request inside two async context managers:
            - the outer one acquires a rate-limiter token (self._rate_limiter) so requests are throttled,
            - and the inner one opens an HTTP POST using the client's session to self.token_endpoint with form-encoded data and an explicit Content-Type header.
        raise_for_status=False disables aiohttp's automatic exception-on-error behavior,so the code checks resp.status manually.
        If the response status is 401 it awaits resp.text() to read the response body and raises WorkdayAuthError (a subclass of WorkdayError)
            to signal invalid credentials and stop the connector. If the status is anything other than 200 it again reads the body and raises a generic WorkdayError
            with the status and text for diagnostics.
            Only when status == 200 does it await resp.json() to parse the successful token payload into token_data.
        A few practical notes/gotchas:
            resp.text() and resp.json() are coroutines that read and cache the response body;
            calling text before json is safe because the implementation stores the body, but it does duplicate decode work and can be wasteful on large responses.
            The json() implementation also checks Content-Type and will raise ContentTypeError if the response MIME type isn’t acceptable,
            so a malformed or non-JSON success response could still raise.
            Finally, ordering matters here (401 handled before the generic non-200 branch) so auth-specific errors are surfaced distinctly.
        """
        async with self._rate_limiter:
            async with self._session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                raise_for_status=False
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

    async def fetch_activity_logs(self, from_time: datetime, to_time: datetime, limit: int = 1000, offset: int = 0) -> List[Dict]:
        if not self._session:
            raise WorkdayError("HTTP session not initialized")

        url = f"{self.base_url}/activityLogging"
        params = {
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "to": to_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "limit": limit,
            "offset": offset,
            "instancesReturned": 1
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

            """
            The outer line async with self._rate_limiter:
                enters an asynchronous context manager that enforces throttling. 
                In practice self._rate_limiter is expected to implement __aenter__/__aexit__ async methods (for example an async semaphore, token-bucket,
                or a custom wait/delay object).
                That context holds until the limiter grants permission,
                so the HTTP request inside will only run according to your rate limits (concurrency limit, delay between requests, etc.).
            The inner line async with self._session.get(..., raise_for_status=False) as resp:
                opens an HTTP GET request using the session object and also uses an async context manager for the response.
                In common async HTTP libraries (e.g., aiohttp) session.get() returns a request/response context manager;
                using async with ensures the response object is properly closed/released when the block exits, preventing connection leaks.
            The params=params and headers=headers arguments add query parameters and request headers to the GET.
                raise_for_status=False disables automatic exception raising for 4xx/5xx responses:
                    the call won’t throw on error status codes, so the code that follows must explicitly inspect resp.status,
                    call await resp.text()/await resp.json() and handle error conditions.
            """
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
