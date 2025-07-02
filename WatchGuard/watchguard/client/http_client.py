from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable

import aiohttp
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger
from pydantic.v1 import BaseModel

from watchguard.client.errors import WatchGuardAuthError, WatchGuardError
from watchguard.client.security_event import SecurityEvent


class WatchGuardClientConfig(BaseModel):
    """
    Configuration for the WatchGuard client.
    """

    username: str
    password: str
    account_id: str
    application_key: str
    base_url: str = "https://api.deu.cloud.watchguard.com"


class WatchGuardClient(object):
    _session: ClientSession | None = None
    _rate_limiter_daily: AsyncLimiter | None = None
    _rate_limiter_second: AsyncLimiter | None = None
    _auth_token: str | None = None

    def __init__(
        self,
        config: WatchGuardClientConfig,
    ) -> None:
        """
        Initialize the WatchGuardClient with the provided credentials and base URL.

        Args:
            config: WatchGuardClientConfig
        """
        self.config = config
        self._rate_limiter_second = AsyncLimiter(max_rate=500, time_period=1)  # 500 requests per second
        self._rate_limiter_daily = AsyncLimiter(max_rate=200_000, time_period=86400)  # 200,000 requests per day

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession, None]:
        """
        Get configured session with rate limiter.

        Returns:
            AsyncGenerator[ClientSession, None]:
        """
        if self._session is None:
            self._session = ClientSession()

        if self._rate_limiter_daily and self._rate_limiter_second:
            async with self._rate_limiter_daily:
                async with self._rate_limiter_second:
                    yield self._session
        else:
            yield self._session

    async def fetch_auth_token(self) -> str:
        """
        Fetch the authentication token from the WatchGuard API.

        Returns:
            str: The authentication token.
        """
        async with self.session() as session:
            response = await session.post(
                f"{self.config.base_url}/oauth/token",
                auth=aiohttp.BasicAuth(self.config.username, self.config.password),
                data={"grant_type": "client_credentials", "scope": "api-access"},
            )

            if response.status != 200:
                raise await WatchGuardError.from_response(response)

            data = await response.json()

            result: str | None = data.get("access_token")
            if not result:
                raise ValueError(f"WatchGuard auth response does not contain a access token. Response: {data}")

        return result

    async def _call_with_auth(self, func: Callable[[str], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        """
        Call a function with authentication.

        Args:
            func: A callable that takes the base URL and returns a dictionary.

        Returns:
            dict[str, Any]: The result of the function call.
        """
        if not self._auth_token:
            self._auth_token = await self.fetch_auth_token()

        try:
            return await func(self._auth_token)
        except WatchGuardAuthError:
            # If authentication fails, fetch a new token and retry
            self._auth_token = await self.fetch_auth_token()

            return await func(self._auth_token)

    async def fetch_data(self, security_event: SecurityEvent, period: int = 1) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch data from the WatchGuard API.

        Args:
            security_event: SecurityEvent
            period: int

        Yields:
            dict[str, Any]: The fetched data.
        """
        # https://www.watchguard.com/help/docs/API/Content/en-US/endpoint_security/WES_endpoint_security/v1/WES_endpoint_security.html#Retrieve_Security_Events_for_Devices_..184
        if period not in [1, 7]:
            raise ValueError("Period must be either 1 or 7 days.")

        async with self.session() as session:

            async def fetch_func(auth_token: str) -> dict[str, Any]:
                headers = {"WatchGuard-API-Key": self.config.application_key, "Authorization": f"Bearer {auth_token}"}

                response = await session.get(
                    "{0}/rest/endpoint-security/management/api/v1/accounts/{1}/securityevents/{2}/export/{3}".format(
                        self.config.base_url, self.config.account_id, security_event.value, period
                    ),
                    headers=headers,
                )

                if response.status != 200:
                    raise await WatchGuardError.from_response(response)

                result: dict[str, Any] = await response.json()

                return result

            data = await self._call_with_auth(fetch_func)

            if data is None:
                logger.warning(
                    "No data returned from WatchGuard API for security event {security_event.value} with period {period}.",
                    security_event=security_event,
                    period=period,
                )

                return

            for item in data.get("data", []):
                yield item

    async def close(self) -> None:
        """
        Close the WatchGuard client session.

        This method should be called when the client is no longer needed to release resources.
        """
        if self._session:
            await self._session.close()
            self._session = None
            self._rate_limiter_daily = None
            self._rate_limiter_second = None
