"""Trellix http client."""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, List, Optional, Set

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from yarl import URL

from .schemas.attributes.epo_events import EpoEventAttributes
from .schemas.edr import TrellixEdrResponse
from .schemas.token import Scope
from .token_refresher import TrellixTokenRefresher


class TrellixHttpClient(object):
    """Class for Trellix http client."""

    _client: Optional["TrellixHttpClient"] = None
    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        api_key: str,
        auth_url: str,
        base_url: str,
        rate_limiter: AsyncLimiter | None = None,
    ):
        """
        Initialize TrellixHttpClient.

        Args:
            client_id: str
            client_secret: str
            api_key: str
            auth_url: str
            base_url: str
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.auth_url = auth_url
        self.base_url = base_url
        if rate_limiter:
            self.set_rate_limiter(rate_limiter)

    @classmethod
    async def instance(
        cls,
        client_id: str,
        client_secret: str,
        api_key: str,
        auth_url: str,
        base_url: str,
        rate_limiter: AsyncLimiter | None = None,
    ) -> "TrellixHttpClient":
        """
        Get instance of TrellixHttpClient.

        Args:
            client_id: str
            client_secret: str
            api_key: str
            auth_url: str
            base_url: str

        Returns:
            TrellixHttpClient:
        """
        if not cls._client:
            cls._client = TrellixHttpClient(client_id, client_secret, api_key, auth_url, base_url, rate_limiter)

        return cls._client

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

        Yields:
            AsyncGenerator[ClientSession, None]:
        """
        if cls._session is None:
            cls._session = ClientSession()

        if cls._rate_limiter:
            async with cls._rate_limiter:
                yield cls._session
        else:
            yield cls._session

    async def _get_token_refresher(self, scopes: Set[Scope]) -> TrellixTokenRefresher:
        """
        Get token refresher.

        Args:
            scopes: Set[Scope]

        Returns:
            TrellixTokenRefresher:
        """
        return await TrellixTokenRefresher.instance(
            self.client_id, self.client_secret, self.api_key, self.auth_url, scopes
        )

    async def _request_headers(self, scopes: Set[Scope], encoding: bool = True) -> dict[str, str]:
        """
        Get authentication header with api key for defined scopes.

        Safe to reuse. It will not do additional request if token is still alive.

        Returns:
            dict[str, str]:
        """

        token_refresher = await self._get_token_refresher(scopes)
        async with token_refresher.with_access_token() as trellix_token:
            headers = {
                "x-api-key": self.api_key,
                "Authorization": "Bearer {0}".format(trellix_token.token.access_token),
            }

            if encoding:
                headers["Content-Type"] = "application/vnd.api+json"

            return headers

    def epo_events_url(self, start_date: datetime, limit: int = 10) -> URL:
        """
        Get EPO events url.

        Args:
            start_date: datetime
            limit: 10

        Returns:
            URL:
        """
        params = {
            "sort": "timestamp",
            "filter": '{"GT": {"timestamp": "' + start_date.strftime("%Y-%m-%dT%H:%M:%SZ") + '"}}',
            "page[limit]": str(limit),
        }

        return URL("{0}/epo/v2/events".format(self.base_url)).with_query(params)

    async def get_epo_events(
        self, start_date: datetime, limit: int = 10
    ) -> List[TrellixEdrResponse[EpoEventAttributes]]:
        """
        Get EPO events.

        Args:
            start_date: datetime
            limit: 10

        Returns:
            List[TrellixEdrResponse[EpoEventAttributes]]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.epo_events_url(start_date, limit)

        async with self.session() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(
                        "Error while getting EPO events with status {0}: {1}".format(
                            response.status, await response.text()
                        ),
                    )

                data = await response.json()

        return [TrellixEdrResponse[EpoEventAttributes](**result) for result in data["data"]]
