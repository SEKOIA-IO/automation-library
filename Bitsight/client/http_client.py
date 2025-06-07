"""Bitsight Http Client and other helpers."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator

from aiohttp import BasicAuth, ClientSession
from aiolimiter import AsyncLimiter
from yarl import URL


class BitsightClient(object):
    """
    Bitsight Http Client.

    Contains all necessary methods to interact with Bitsight API.
    """

    def __init__(self, api_key: str, rate_limiter: AsyncLimiter | None = None) -> None:
        """
        Initialize BitsightClient.

        Args:
            api_key: str
            rate_limiter: AsyncLimiter | None
        """
        self.api_key = api_key
        self._rate_limiter: AsyncLimiter = rate_limiter or self.default_limiter()
        # We can't have more than 3 concurrent requests
        # https://help.bitsighttech.com/hc/en-us/articles/360036941374-Errors-and-Status-Codes#429
        self._concurrency_limiter = asyncio.Semaphore(3)
        self._session = ClientSession()

    @classmethod
    def default_limiter(cls) -> AsyncLimiter:
        """
        Get default rate limiter.

        Returns:
            aiolimiter.AsyncLimiter:
        """
        # https://help.bitsighttech.com/hc/en-us/articles/360036941374-Errors-and-Status-Codes
        # 16 requests per second to stay under 5000 requests per 5 minutes
        # 5000 requests per 5 minutes = 16.666 requests per second
        return AsyncLimiter(16, 1)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession, None]:
        """
        Get configured session with rate limiter.

        Yields:
            AsyncGenerator[ClientSession, None]:
        """
        # Add concurrency to the session
        async with self._concurrency_limiter:
            async with self._rate_limiter:
                yield self._session

    def get_auth(self) -> BasicAuth:
        """
        Get BasicAuth object.

        Returns:
            aiohttp.BasicAuth:
        """
        return BasicAuth(self.api_key, "")

    @staticmethod
    def get_url(company_id: str, last_seen: str | None = None, offset: int | None = None) -> URL:
        """
        Get company url.

        Doc:
            https://help.bitsighttech.com/hc/en-us/articles/360022913734-GET-Finding-Details#example-request

        Args:
            company_id: str
            last_seen: str | None
            offset: int | None

        Returns:
            str:
        """
        base_url = f"https://api.bitsighttech.com/ratings/v1/companies/{company_id}/findings"

        # TODO: in spec we want to use `last_seen_gt`. Seems like `last_seen_gt` does not include the items inside last_seen
        #       but as we use offset, we should use `last_seen` instead
        # Sort is default
        params = {
            "last_seen": last_seen,
            "offset": offset,
            # "limit": 100,  # Max value from docs
        }

        filtered_params: dict[str, str | int] = {key: value for key, value in params.items() if value is not None}

        return URL(base_url).with_query(filtered_params)

    async def get_findings(
        self,
        company_id: str | None = None,
        url: str | None = None,
        last_seen: str | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get findings for a company.

        Args:
            url: str | None
            company_id: str | None
            last_seen: str | None
            offset: int | None

        Returns:
            tuple[list[dict[str, Any]], str | None]: Findings, error message.
        """
        _url: str | None = url
        if company_id and not url:
            _url = str(self.get_url(company_id, last_seen, offset))

        if not _url:
            raise ValueError("company_id or url must be provided")

        async with self.session() as session:
            async with session.get(_url, auth=self.get_auth()) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to get findings: {response.status}: {await response.text()}")

                result = await response.json()

                next_url: str | None = result.get("links", {}).get("next")
                findings: list[dict[str, Any]] = result.get("results", [])

                return findings, next_url

    async def findings_result(
        self, company_id: str, last_seen: str | None = None, offset: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Get findings generator.

        Args:
            company_id: str
            last_seen: str | None
            offset: int | None

        Yields:
            dict[str, Any]:
        """
        next_url = None

        while True:
            findings, next_url = await self.get_findings(
                company_id=company_id, url=next_url, last_seen=last_seen, offset=offset
            )

            for finding in findings:
                yield finding

            if not next_url:
                break
