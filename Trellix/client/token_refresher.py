"""Auth token refresher."""

import asyncio
import time
from asyncio import Lock, Task
from contextlib import asynccontextmanager
from posixpath import join as urljoin
from typing import AsyncGenerator, Optional, Set
from urllib.parse import urlencode

from aiohttp import BasicAuth, ClientSession
from loguru import logger
from yarl import URL

from .errors import APIError, AuthenticationFailed
from .schemas.token import HttpToken, Scope, TrellixToken


class TrellixTokenRefresher(object):
    """
    Contains access token refresher logic.

    Example of usage:
    >>> from client.token_refresher import TrellixTokenRefresher
    >>>
    >>> token_refresher = TrellixTokenRefresher(**config)
    >>>
    >>> async with token_refresher.get_access_token() as access_token:
    >>>     print(access_token)
    """

    _instances: dict[str, "TrellixTokenRefresher"] = {}
    _locks: dict[str, Lock] = {}
    _session: ClientSession | None = None

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        api_key: str,
        base_url: str,
        scopes: Set[Scope],
    ):
        """
        Initialize TrellixTokenRefresher.

        Each set of scopes will have its own access token with refreshing logic.

        Args:
            client_id: str
            client_secret: str
            api_key: str
            base_url: str
            scopes: Set[Scope]
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.base_url = base_url
        self.scopes = scopes

        self._token: TrellixToken | None = None
        self._token_refresh_task: Optional[Task[None]] = None

    @classmethod
    def session(cls) -> ClientSession:
        """
        Initialize client session.

        Singleton client session to work with token refresh logic.

        Returns:
            ClientSession:
        """
        if not cls._session:
            cls._session = ClientSession()

        return cls._session

    @classmethod
    async def instance(
        cls,
        client_id: str,
        client_secret: str,
        api_key: str,
        auth_url: str,
        scopes: Set[Scope],
    ) -> "TrellixTokenRefresher":
        """
        Get singleton TrellixTokenRefresher instance for specified set of scopes.

        Args:
            client_id: str
            client_secret: str
            api_key: str
            auth_url: str
            scopes: Set[Scope]

        Returns:
            TrellixTokenRefresher:
        """
        refresher_unique_key = str(frozenset(scopes))
        if not cls._locks.get(refresher_unique_key):
            cls._locks[refresher_unique_key] = asyncio.Lock()

        if not cls._instances.get(refresher_unique_key):
            async with cls._locks[refresher_unique_key]:
                if not cls._instances.get(refresher_unique_key):
                    cls._instances[refresher_unique_key] = TrellixTokenRefresher(
                        client_id, client_secret, api_key, auth_url, scopes
                    )

        return cls._instances[refresher_unique_key]

    @property
    def auth_url(self) -> URL:
        params = {
            "grant_type": "client_credentials",
            "scope": "+".join(self.scopes),
        }

        auth_url = self.base_url
        if not auth_url.endswith("/token"):
            auth_url = urljoin(auth_url, "token")

        return URL(auth_url).with_query(urlencode(params, safe="+", encoding="utf-8"))

    async def refresh_token(self) -> None:
        """
        Refresh token based on class configuration.

        Also triggers token refresh task.
        """
        headers = {"x-api-header": self.api_key}

        async with self.session().post(
            self.auth_url,
            headers=headers,
            auth=BasicAuth(self.client_id, self.client_secret),
            json={},
        ) as response:
            logger.debug(response.url)

            # raise an exception for any server error
            if response.status >= 500:
                error_description = await response.text()
                raise APIError(error_description)

            response_data = await response.json()

            # raise an exception for any client error
            if response.status >= 400:
                raise AuthenticationFailed.from_http_response(response_data)

            access_token = HttpToken(**response_data)
            logger.info(
                "Got new access token with expiration in {expires_in} at {created_at}",
                expires_in=access_token.expires_in,
                created_at=time.time(),
            )

            self._token = TrellixToken(
                token=access_token,
                scopes=self.scopes,
                created_at=time.time(),
            )

            await self._schedule_token_refresh(self._token.token.expires_in)

    def _compute_refresh_time(self, expires_in: int) -> int:
        """
        Compute a refresh intervale with a safety margin
        This margin is depends on the refresh interval and a maximum of five minutes.
        The refresh interval is a minimum of 30 seconds
        """
        # delta = min(300, int(expires_in / 6))
        # return max(30, expires_in - delta)

        return min(300, expires_in)

    async def _schedule_token_refresh(self, expires_in: int) -> None:
        """
        Schedule token refresh.

        Args:
            expires_in: int
        """
        await self.close()

        refresh_in = self._compute_refresh_time(expires_in)

        logger.info("Scheduling token refresh in {refresh_in} seconds {at}", refresh_in=refresh_in, at=time.time())

        async def _refresh() -> None:
            await asyncio.sleep(refresh_in)
            await self.refresh_token()

        self._token_refresh_task = asyncio.create_task(_refresh())

    async def close(self) -> None:
        """
        Cancel token refresh task.
        """
        if self._token_refresh_task:
            self._token_refresh_task.cancel()

    @asynccontextmanager
    async def with_access_token(self) -> AsyncGenerator[TrellixToken, None]:  # pragma: no cover
        """
        Get access token.

        Yields:
            TrellixToken:
        """
        if self._token is None or self._token.is_expired():
            await self.refresh_token()

        if not self._token:
            raise ValueError("Token is not initialized")

        yield self._token
