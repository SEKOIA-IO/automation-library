"""Contains client to interact with Github API."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter

from github_modules.async_client.token_refresher import PemGithubTokenRefresher


class AsyncGithubClient(object):
    """Async Github client."""

    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(
        self,
        organization: str,
        api_key: str | None = None,
        pem_file: str | None = None,
        app_id: int | None = None,
        rate_limiter: AsyncLimiter | None = None,
    ):
        """

        Args:
            organization: str
            api_key: str | None
            pem_file: str | None
            app_id: int | None
            rate_limiter: AsyncLimiter | None
        """
        if not api_key and not pem_file:
            raise ValueError("Either api key or pem file must be provided")

        self.api_key = api_key

        self.pem_file = pem_file
        self.organization = organization
        self.app_id = app_id

        if rate_limiter:
            self.set_rate_limiter(rate_limiter)

    @classmethod
    def set_rate_limiter(cls, rate_limiter: AsyncLimiter) -> None:
        """
        Set rate limiter.

        Args:
            rate_limiter:
        """
        cls._rate_limiter = rate_limiter

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[ClientSession, None]:
        """
        Get configured session with rate limiter.

        Returns:
            AsyncGenerator[ClientSession, None]:
        """
        if cls._session is None:
            cls._session = ClientSession()

        if cls._rate_limiter:
            async with cls._rate_limiter:
                yield cls._session
        else:
            yield cls._session

    async def _get_token_refresher(self) -> PemGithubTokenRefresher:
        """
        Get token refresher.

        Returns:
            PemGithubTokenRefresher:
        """
        if not self.pem_file or not self.app_id:
            raise ValueError("Pem file, organization and app id should be provided.")

        return await PemGithubTokenRefresher.instance(
            self.pem_file,
            self.organization,
            self.app_id,
        )

    async def get_auth_headers(self) -> dict[str, str]:
        """Get auth headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.api_key:
            headers["Authorization"] = "token {0}".format(self.api_key)
        else:
            token_refresher = await self._get_token_refresher()
            token = await token_refresher.get_access_token()

            headers["Authorization"] = "Bearer {0}".format(token)

        return headers

    @property
    def audit_logs_url(self) -> str:
        """
        Gets url to get audit logs for organization.

        Returns:
            str:
        """
        return "https://api.github.com/orgs/{0}/audit-log".format(self.organization)

    async def get_audit_logs(self, start_from: int) -> list[dict[str, Any]]:
        """
        Get audit logs data.

        Args:
            start_from:

        Returns:
            list[dict[str, Any]]:
        """
        print(start_from)
        params = {"phrase": "created:>{0}".format(start_from), "order": "asc"}

        async with self.session() as session:
            headers = await self.get_auth_headers()

            async with session.get(self.audit_logs_url, params=params, headers=headers) as response:
                result: list[dict[str, Any]] = await response.json()

                return result
