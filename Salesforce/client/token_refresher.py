"""Auth token refresher."""

import asyncio
import time
from asyncio import Lock, Task
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from urllib.parse import urlencode

from aiohttp import BasicAuth, ClientSession
from loguru import logger
from yarl import URL

from .schemas.token import HttpToken, SalesforceToken


class SalesforceTokenRefresher(object):
    """
    Contains access token refresher logic.

    Example of usage:
    >>> from client.token_refresher import SalesforceTokenRefresher
    >>>
    >>> token_refresher = SalesforceTokenRefresher(**config)
    >>>
    >>> async with token_refresher.with_access_token() as access_token:
    >>>     print(access_token)
    """

    _instances: dict[str, "SalesforceTokenRefresher"] = {}
    _locks: dict[str, Lock] = {}
    _session: ClientSession | None = None

    def __init__(self, client_id: str, client_secret: str, auth_url: str, token_ttl: int = 300):
        """
        Initialize SalesforceTokenRefresher.

        Each set of scopes will have its own access token with refreshing logic.

        Args:
            client_id: str
            client_secret: str
            auth_url: str
            token_ttl: int
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url
        self.token_ttl = token_ttl

        self._token: SalesforceToken | None = None
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
        cls, client_id: str, client_secret: str, auth_url: str, token_ttl: int = 3600
    ) -> "SalesforceTokenRefresher":
        """
        Get singleton SalesforceTokenRefresher instance for specified set of scopes.

        Args:
            client_id: str
            client_secret: str
            auth_url: str
            token_ttl: int

        Returns:
            SalesforceTokenRefresher:
        """
        refresher_unique_key = str(frozenset({client_id, client_secret, auth_url, token_ttl}))
        if not cls._locks.get(refresher_unique_key):
            cls._locks[refresher_unique_key] = asyncio.Lock()

        if not cls._instances.get(refresher_unique_key):
            async with cls._locks[refresher_unique_key]:
                if not cls._instances.get(refresher_unique_key):
                    cls._instances[refresher_unique_key] = SalesforceTokenRefresher(
                        client_id,
                        client_secret,
                        auth_url,
                        token_ttl,
                    )

        return cls._instances[refresher_unique_key]

    async def refresh_token(self) -> None:
        """
        Refresh token based on class configuration.

        Also triggers token refresh task.
        """
        params = {
            "grant_type": "client_credentials",
        }

        url = URL("{0}/services/oauth2/token".format(self.auth_url)).with_query(urlencode(params, encoding="utf-8"))

        async with self.session().post(url, auth=BasicAuth(self.client_id, self.client_secret), json={}) as response:
            response_data = await response.json()

            try:
                self._token = SalesforceToken(
                    token=HttpToken(**response_data),
                    created_at=time.time(),
                    ttl=self.token_ttl,
                )
            except Exception as e:
                logger.info(
                    "Cannot get token. Response contains {0} status {1}".format(response_data, response.status)
                )

                raise e

            await self._schedule_token_refresh(self._token.ttl)

    async def _schedule_token_refresh(self, expires_in: int) -> None:
        """
        Schedule token refresh.

        Args:
            expires_in: int
        """
        await self.close()

        async def _refresh() -> None:
            await asyncio.sleep(expires_in)
            await self.refresh_token()

        self._token_refresh_task = asyncio.create_task(_refresh())

    async def close(self) -> None:
        """
        Cancel token refresh task.
        """
        if self._token_refresh_task:
            self._token_refresh_task.cancel()

    @asynccontextmanager
    async def with_access_token(self) -> AsyncGenerator[SalesforceToken, None]:
        """
        Get access token.

        Yields:
            SalesforceToken:
        """
        if self._token is None:
            await self.refresh_token()

        if not self._token:
            raise ValueError("Token is not initialized")

        yield self._token
