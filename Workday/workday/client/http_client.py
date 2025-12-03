# workday/client/http_client.py
import aiohttp
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from aiolimiter import AsyncLimiter
from workday.client.errors import WorkdayError, WorkdayAuthError, WorkdayRateLimitError
import logging


class WorkdayClient:
    def __init__(
        self,
        workday_host: str,
        tenant_name: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_endpoint: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.workday_host = workday_host
        self.tenant_name = tenant_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._explicit_token_endpoint = token_endpoint
        self.logger = logger or logging.getLogger(__name__)

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._rate_limiter = AsyncLimiter(max_rate=10, time_period=1)
        self._session: Optional[aiohttp.ClientSession] = None

        self.logger.info(
            f"WorkdayClient initialized - Host: {workday_host}, Tenant: {tenant_name}, "
            f"Client ID: {client_id[:8]}..., Token endpoint: {self.token_endpoint}"
        )

    @property
    def base_url(self) -> str:
        return f"https://{self.workday_host}/ccx/api/privacy/v1/{self.tenant_name}"

    @property
    def token_endpoint(self) -> str:
        if self._explicit_token_endpoint:
            return self._explicit_token_endpoint
        return f"https://{self.workday_host}/ccx/oauth2/{self.tenant_name}/token"

    async def _get_access_token(self) -> str:
        if self._session is None:
            self.logger.error("HTTP session not initialized when trying to get access token")
            raise WorkdayError("HTTP session not initialized")

        # return cached if valid
        if self._access_token and self._token_expires_at:
            now = datetime.now(timezone.utc)
            if now < self._token_expires_at:
                time_until_expiry = (self._token_expires_at - now).total_seconds()
                self.logger.debug(
                    f"Using cached access token (expires in {time_until_expiry:.0f}s at {self._token_expires_at.isoformat()})"
                )
                return self._access_token
            else:
                self.logger.info(
                    f"Access token expired at {self._token_expires_at.isoformat()}, refreshing..."
                )

        self.logger.info(f"Requesting new access token from {self.token_endpoint}")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        self.logger.debug(
            f"Token request payload: grant_type={data['grant_type']}, "
            f"client_id={self.client_id[:8]}..., refresh_token={self.refresh_token[:8]}..."
        )

        async with self._rate_limiter:
            self.logger.debug("Rate limiter acquired for token request")
            
            async with self._session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                raise_for_status=False,
            ) as resp:
                status = resp.status
                headers = dict(resp.headers)
                
                self.logger.info(f"Token endpoint response: Status {status}")
                self.logger.debug(f"Token response headers: {headers}")
                
                if status == 401:
                    text = await resp.text()
                    self.logger.error(
                        f"Token exchange UNAUTHORIZED (401) - Response body: {text}"
                    )
                    raise WorkdayAuthError(f"Token exchange unauthorized: {text}")
                
                if status != 200:
                    text = await resp.text()
                    self.logger.error(
                        f"Token request FAILED with status {status} - Response: {text}"
                    )
                    raise WorkdayError(f"Token request failed ({status}): {text}")
                
                token_data = await resp.json()
                self.logger.debug(f"Token data keys received: {list(token_data.keys())}")

        self._access_token = token_data.get("access_token")
        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
        
        self.logger.info(
            f"Access token obtained successfully - "
            f"Token: {self._access_token[:12] if self._access_token else 'None'}..., "
            f"Expires in: {expires_in}s (cached until {self._token_expires_at.isoformat()})"
        )
        
        return self._access_token

    async def fetch_activity_logs(
        self, from_time: datetime, to_time: datetime, limit: int = 1000, offset: int = 0
    ) -> List[Dict[str, Any]]:
        if not self._session:
            self.logger.error("HTTP session not initialized when fetching activity logs")
            raise WorkdayError("HTTP session not initialized")

        url = f"{self.base_url}/activityLogging"
        self.logger.warning(f"[DEBUG] Activity Logging URL = {url}")
        
        params: Dict[str, str] = {
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "to": to_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "limit": str(limit),
            "offset": str(offset),
            "instancesReturned": "1",
        }

        self.logger.info(
            f"Fetching activity logs - URL: {url}, "
            f"Time range: {params['from']} to {params['to']}, "
            f"Limit: {limit}, Offset: {offset}"
        )
        self.logger.debug(f"Request params: {params}")

        headers = {"Accept": "application/json"}

        max_attempts = 3
        attempt = 0
        backoff_base = 2

        while attempt < max_attempts:
            attempt += 1
            self.logger.info(f"Activity log request attempt {attempt}/{max_attempts}")
            
            # ensure token
            access_token = await self._get_access_token()
            headers["Authorization"] = f"Bearer {access_token}"
            self.logger.debug(f"Authorization header set with token: {access_token[:12]}...")

            async with self._rate_limiter:
                self.logger.debug("Rate limiter acquired for activity log request")
                
                async with self._session.get(url, params=params, headers=headers, raise_for_status=False) as resp:
                    status = resp.status
                    response_headers = dict(resp.headers)
                    
                    self.logger.info(f"Activity log response: Status {status}")
                    self.logger.debug(f"Response headers: {response_headers}")
                    
                    # 401: try refreshing once
                    if status == 401:
                        self.logger.warning(
                            f"Received 401 Unauthorized on attempt {attempt}/{max_attempts} - "
                            "Invalidating token and retrying"
                        )
                        self._access_token = None
                        self._token_expires_at = None
                        
                        if attempt < max_attempts:
                            await sleep(0.5)
                            self.logger.debug("Paused 0.5s before retry after 401")
                            continue
                        
                        self.logger.error("Max attempts reached after 401, raising WorkdayAuthError")
                        raise WorkdayAuthError("Unauthorized when fetching activity logs")
                    
                    if status == 429:
                        ra = resp.headers.get("Retry-After")
                        wait = 60
                        if ra:
                            try:
                                wait = int(ra)
                                self.logger.info(f"Rate limited (429) - Retry-After header: {ra}s")
                            except Exception as e:
                                self.logger.warning(
                                    f"Could not parse Retry-After header '{ra}': {e}, using default {wait}s"
                                )
                        
                        wait = wait * (backoff_base ** (attempt - 1))
                        self.logger.warning(
                            f"Rate limited (429) on attempt {attempt}/{max_attempts} - "
                            f"Waiting {wait}s before retry"
                        )
                        await sleep(wait)
                        continue
                    
                    if status != 200:
                        text = await resp.text()
                        self.logger.error(
                            f"Activity log request FAILED with status {status} - Response: {text}"
                        )
                        raise WorkdayError(f"ActivityLogging request failed ({status}): {text}")
                    
                    data = await resp.json()
                    event_count = len(data) if isinstance(data, list) else "unknown"
                    self.logger.info(
                        f"Successfully fetched activity logs - "
                        f"Events received: {event_count}, Offset: {offset}"
                    )
                    self.logger.debug(f"Response data type: {type(data)}, Sample: {str(data)[:200]}")
                    
                    return data

        self.logger.error(f"Exceeded maximum retry attempts ({max_attempts}) for activity logs")
        raise WorkdayRateLimitError("Exceeded maximum retry attempts while fetching activity logs")

    async def __aenter__(self):
        self.logger.info("Entering WorkdayClient context - Creating aiohttp session")
        self._session = aiohttp.ClientSession()
        
        # Validate token immediately at __aenter__ to fail fast on bad credentials
        self.logger.info("Validating credentials by requesting initial access token")
        try:
            await self._get_access_token()
            self.logger.info("Initial token validation successful")
        except Exception as e:
            self.logger.error(f"Initial token validation FAILED: {e}")
            raise
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info(
            f"Exiting WorkdayClient context - Exception: {exc_type.__name__ if exc_type else 'None'}"
        )
        if self._session:
            await self._session.close()
            self.logger.debug("aiohttp session closed")