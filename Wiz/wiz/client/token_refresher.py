"""Auth token refresher."""

import asyncio
import time
from asyncio import Lock, Task
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from aiohttp import ClientSession
from loguru import logger
from pydantic.main import BaseModel


class WizToken(BaseModel):
    """
    Token model.

    Example:
        {
         "access_token":"eyJz93a...k4laUWw",
         "refresh_token": "eyJj….Bw",
         "token_type":"Bearer",
         "expires_in":86400
        }
    """

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: float
    created_at: float

    def is_expired(self) -> bool:
        """
        Check if token is expired.

        Returns:
            bool:
        """
        return time.time() >= self.created_at + self.expires_in


class WizTokenRefresher(object):
    """
    Contains access token refresher logic.
    """

    _locks: Lock | None = None
    _session: ClientSession | None = None

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        oauth_url: str,
    ):
        """
        Initialize WizTokenRefresher.

        Each set of scopes will have its own access token with refreshing logic.

        Args:
            client_id: str
            client_secret: str
            base_url: str
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_url = oauth_url

        self._token: WizToken | None = None
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

    async def refresh_token(self) -> None:
        """
        Refresh token based on class configuration.

        Also triggers token refresh task.

        Example of request:
        curl --request POST \
             --url <TOKEN_URL> \
             --header 'accept: application/json' \
             --header 'content-type: application/x-www-form-urlencoded' \
             --data grant_type=client_credentials \
             --data audience=wiz-api \
             --data client_id=<CLIENT_ID> \
             --data client_secret=<CLIENT_SECRET>
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "client_credentials",
            "audience": "wiz-api",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with self.session().post(
            self.oauth_url,
            headers=headers,
            data=data,
        ) as response:
            response_data = await response.json()
            self._token = WizToken(
                **{
                    **response_data,
                    # "expires_in": 4, # for testing purposes only
                    "created_at": time.time(),
                }
            )

            logger.info(
                "Got new access token with expiration in {expires_in} at {created_at}",
                expires_in=self._token.expires_in,
                created_at=self._token.created_at,
            )

            await self._schedule_token_refresh(self._token.expires_in)

    async def _schedule_token_refresh(self, expires_in: float) -> None:
        """
        Schedule token refresh.

        Args:
            expires_in: int
        """
        await self.close()

        refresh_in = expires_in - 1

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
    async def with_access_token(self) -> AsyncGenerator[WizToken, None]:  # pragma: no cover
        """
        Get access token.

        Yields:
            WizToken:
        """
        if self._token is None or self._token.is_expired():
            await self.refresh_token()

        if not self._token:
            raise ValueError("Token is not initialized")

        yield self._token

    @staticmethod
    def create_url_from_tenant(tenant_url: str) -> str:
        """
        Function match input url to contain correct tenant path.

        Wiz Commercial https://auth.app.wiz.io/oauth/token
        Wiz for Gov (FedRAMP) https://auth.app.wiz.us/oauth/token
        Wiz Commercial hosted on AWS GovCloud https://auth.gov.wiz.io/oauth/token

        Args:
            tenant_url: str

        Returns:
            str:
        """
        if "app.wiz.us" in tenant_url:
            return "https://auth.app.wiz.us/oauth/token"
        elif "app.wiz.io" in tenant_url:
            return "https://auth.app.wiz.io/oauth/token"
        else:
            return "https://auth.gov.wiz.io/oauth/token"
