"""Contains client to interact with Github API."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Union

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from multidict import MultiDictProxy
from yarl import URL

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

    async def get_auth_headers(self, refresh_token: bool = False) -> dict[str, str]:
        """Get auth headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.api_key:
            headers["Authorization"] = "token {0}".format(self.api_key)
        else:
            token_refresher = await self._get_token_refresher()
            if refresh_token:
                await token_refresher.refresh_token()

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

    async def _get_audit_logs(
        self, start_from: int, url: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get audit logs data.

        Args:
            start_from:

        Returns:
            list[dict[str, Any]]:
        """
        params = {} if url else {"phrase": "created:>{0}".format(start_from), "order": "asc", "per_page": 100}
        request_url = url or self.audit_logs_url

        result: list[dict[str, Any]] = []
        links: Union[MultiDictProxy[Union[str, URL]], dict[Any, Any]] = {}
        next_link: str | None = None

        async with self.session() as session:
            headers = await self.get_auth_headers()

            async with session.get(request_url, params=params, headers=headers) as response:
                if response.status != 200:
                    headers = await self.get_auth_headers(refresh_token=True)

                    async with session.get(request_url, params=params, headers=headers) as refreshed_response:
                        result = await refreshed_response.json()
                        links = refreshed_response.links.get("next", {})
                        next_link = str(links.get("url")) if links.get("url") else None
                else:
                    result = await response.json()
                    links = response.links.get("next", {})
                    next_link = str(links.get("url")) if links.get("url") else None

                return result, next_link

    async def get_audit_logs(self, start_from: int) -> list[dict[str, Any]]:
        """
        Get audit logs.

        If token is expired - refresh it and try again.

        Args:
            start_from: int

        Returns:
            list[dict[str, Any]]:
        """
        result, next_url = await self._get_audit_logs(start_from)
        while next_url:
            result_part, next_url = await self._get_audit_logs(start_from, next_url)
            result.extend(result_part)

        return result
