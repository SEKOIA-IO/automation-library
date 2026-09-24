# workday/client/http_client.py
import aiohttp
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from aiolimiter import AsyncLimiter
from workday.client.errors import WorkdayError, WorkdayAuthError, WorkdayRateLimitError
from sekoia_automation.trigger import Trigger
from workday.metrics import (
    API_REQUESTS,
    API_REQUEST_DURATION,
    INCOMING_EVENTS,
)


class WorkdayClient:
    def __init__(
        self,
        workday_host: str,
        tenant_name: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_endpoint: Optional[str] = None,
        trigger: Optional[Trigger] = None,
        intake_key: str = "",
    ):
        self.workday_host = workday_host
        self.tenant_name = tenant_name
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._explicit_token_endpoint = token_endpoint
        self.trigger = trigger
        self.intake_key = intake_key

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._rate_limiter = AsyncLimiter(max_rate=10, time_period=1)
        self._session: Optional[aiohttp.ClientSession] = None

    def log(self, message: str, level: str = "info") -> None:
        if self.trigger:
            self.trigger.log(message=message, level=level)

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
            raise WorkdayError("HTTP session not initialized")

        if self._access_token and self._token_expires_at:
            now = datetime.now(timezone.utc)
            if now < self._token_expires_at:
                return self._access_token
            else:
                pass

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with self._rate_limiter:
            start = datetime.now().timestamp()
            async with self._session.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                raise_for_status=False,
            ) as resp:
                duration = datetime.now().timestamp() - start
                status = resp.status
                # Prometheus API metrics for token exchange
                API_REQUESTS.labels(intake_key=self.intake_key, endpoint="token", status_code=status).inc()
                API_REQUEST_DURATION.labels(intake_key=self.intake_key, endpoint="token").observe(duration)

                if status == 401:
                    text = await resp.text()
                    raise WorkdayAuthError(f"Token exchange unauthorized: {text}")

                if status != 200:
                    text = await resp.text()
                    raise WorkdayError(f"Token request failed ({status}): {text}")

                token_data = await resp.json()

        self._access_token = token_data.get("access_token")
        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)

        return self._access_token

    async def fetch_activity_logs(
        self,
        from_time: datetime,
        to_time: datetime,
        limit: int = 1000,
        offset: int = 0,
        instances_returned: int = 1,
    ) -> List[Dict[str, Any]]:
        if not self._session:
            raise WorkdayError("HTTP session not initialized")

        url = f"{self.base_url}/activityLogging"

        params = {
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "to": to_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "limit": str(limit),
            "offset": str(offset),
            # instancesReturned is a multiplier of 10,000 capping the total pool for this window.
            # Hardcoding "1" previously limited every window to 10,000 records (data loss on
            # high-volume tenants). Now driven by the connector configuration.
            "instancesReturned": str(instances_returned),
        }

        headers = {"Accept": "application/json"}

        max_attempts = 3
        attempt = 0
        backoff_base = 1

        while attempt < max_attempts:
            attempt += 1

            access_token = await self._get_access_token()
            headers["Authorization"] = f"Bearer {access_token}"

            async with self._rate_limiter:
                start = datetime.now().timestamp()
                async with self._session.get(url, params=params, headers=headers, raise_for_status=False) as resp:
                    duration = datetime.now().timestamp() - start
                    status = resp.status

                    # Prometheus API metrics
                    API_REQUESTS.labels(
                        intake_key=self.intake_key, endpoint="activityLogging", status_code=status
                    ).inc()
                    API_REQUEST_DURATION.labels(intake_key=self.intake_key, endpoint="activityLogging").observe(
                        duration
                    )

                    if status == 401:
                        self._access_token = None
                        self._token_expires_at = None
                        if attempt < max_attempts:
                            await sleep(0.5)
                            continue
                        raise WorkdayAuthError("Unauthorized when fetching activity logs")

                    if status == 429:
                        ra = resp.headers.get("Retry-After")
                        wait = int(ra) if ra and ra.isdigit() else 60
                        wait *= backoff_base ** (attempt - 1)
                        await sleep(wait)
                        continue

                    if status != 200:
                        text = await resp.text()
                        raise WorkdayError(f"ActivityLogging request failed ({status}): {text}")

                    data = await resp.json()

                    events: list[Any] = []
                    if isinstance(data, dict):
                        candidates = [
                            "data",
                            "ActivityLogEntry",
                            "Report_Entry",
                            "items",
                            "activityLogs",
                        ]
                        for key in candidates:
                            if key in data:
                                events = data[key] or []
                                break
                        else:
                            events = []

                    elif isinstance(data, list):
                        events = data
                    else:
                        events = []

                    if not isinstance(events, list):
                        events = []

                    # Prometheus: events collected
                    if isinstance(events, list):
                        INCOMING_EVENTS.labels(intake_key=self.intake_key).inc(len(events))

                    return events

        raise WorkdayRateLimitError("Exceeded maximum retry attempts while fetching activity logs")

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(trust_env=True)

        try:
            await self._get_access_token()
        except Exception as e:
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
