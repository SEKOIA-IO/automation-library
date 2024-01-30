"""Contains Github token refresher."""

import asyncio
import time
from asyncio import Lock, Task
from typing import Optional

import jwt
from aiohttp import ClientSession
from jwt import JWT


class PemGithubTokenRefresher(object):
    """Github token refresher that uses pem file content and org name to get access token."""

    _instances: dict[str, "PemGithubTokenRefresher"] = {}
    _locks: dict[str, Lock] = {}
    _session: ClientSession | None = None

    def __init__(self, pem_file: str, organization: str, app_id: int, token_ttl: int = 300):
        """
        Initialize GithubTokenRefresher.

        Uses pem_file and organization to get token.
        More info about it:
            https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation

        Args:
            pem_file: str
            organization: str
            token_ttl: int
        """
        if token_ttl > 600:
            raise ValueError("Token ttl can't be more than 600 seconds ( 10 minutes ).")

        self.token_ttl = token_ttl
        self.pem_file = pem_file
        self.organization = organization
        self.app_id = app_id

        self._token: str | None = None
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
        cls, pem_file: str, organization: str, app_id: int, token_ttl: int = 300
    ) -> "PemGithubTokenRefresher":
        """
        Get singleton PemGithubTokenRefresher instance for specified input params.

        Args:
            pem_file: str
            organization: str
            app_id: int
            token_ttl: int

        Returns:
            PemGithubTokenRefresher:
        """
        refresher_unique_key = str(frozenset({pem_file, organization}))
        if not cls._locks.get(refresher_unique_key):
            cls._locks[refresher_unique_key] = asyncio.Lock()

        if not cls._instances.get(refresher_unique_key):
            async with cls._locks[refresher_unique_key]:
                if not cls._instances.get(refresher_unique_key):
                    cls._instances[refresher_unique_key] = PemGithubTokenRefresher(
                        pem_file,
                        organization,
                        app_id,
                        token_ttl,
                    )

        return cls._instances[refresher_unique_key]

    @property
    def installation_request_url(self) -> str:
        """
        Gets url to get installation info by organization.

        Docs:
            https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation#using-an-installation-access-token-to-authenticate-as-an-app-installation

        Returns:
            str:
        """
        return "https://api.github.com/orgs/{0}/installation".format(self.organization)

    @staticmethod
    def access_token_for_installation_url(installation_id: int) -> str:
        """
        Gets url to get access token for installation.

        Args:
            installation_id: int

        Returns:
            str:
        """
        return "https://api.github.com/app/installations/{0}/access_tokens".format(installation_id)

    def _get_jwt(self) -> str:
        """
        Generates jwt token from pem file content with specified ttl.

        Returns:
            str:
        """
        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + self.token_ttl,
            "iss": self.app_id,
        }

        signing_key = jwt.jwk_from_pem(self.pem_file.encode("utf-8"))

        return JWT().encode(payload, signing_key, alg="RS256")

    async def refresh_token(self) -> None:
        """
        Refresh token based on class configuration.

        Also triggers token refresh task.
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer {0}".format(self._get_jwt()),
        }

        session = self.session()

        async with session.get(self.installation_request_url, headers=headers) as installation_response:
            installation_info = await installation_response.json()
            access_token_url = installation_info.get("access_tokens_url")
            async with session.post(access_token_url, headers=headers) as access_token_response:
                access_token_info = await access_token_response.json()

                self._token = access_token_info.get("token")

                await self._schedule_token_refresh(self.token_ttl)

    async def _schedule_token_refresh(self, expires_in: int) -> None:
        """
        Schedule token refresh.

        Args:
            expires_in: int
        """
        await self.close()

        async def _refresh() -> None:  # pragma: no cover
            await asyncio.sleep(expires_in)
            await self.refresh_token()

        self._token_refresh_task = asyncio.create_task(_refresh())

    async def close(self) -> None:
        """
        Cancel token refresh task.
        """
        if self._token_refresh_task:
            self._token_refresh_task.cancel()

    async def get_access_token(self) -> str:
        """
        Get access token.

        Yields:
            str:
        """
        if self._token is None:
            await self.refresh_token()

        if not self._token:  # pragma: no cover
            raise ValueError("Token is not initialized")

        return self._token
