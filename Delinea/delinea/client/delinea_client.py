import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator
from urllib.parse import urlencode

import aiohttp
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter


class DelineaError(Exception):
    @classmethod
    async def from_response(cls, response: aiohttp.ClientResponse) -> "DelineaError":
        try:
            data = await response.json()
        except Exception:
            data = await response.text()

        return cls(f"Error {response.status}: {data}")


class DelineaClient(object):
    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret

        self._access_token: str | None = None
        self._expires_in: int = 60  # 1 minute

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession, None]:  # pragma: no cover
        """
        Get configured session with rate limiter.

        Returns:
            AsyncGenerator[ClientSession, None]:
        """
        if self._session is None:
            self._session = ClientSession()

        if self._rate_limiter:
            async with self._rate_limiter:
                yield self._session
        else:
            yield self._session

    async def get_auth_token(self) -> str:
        """
        Fetch the authentication token from the Delinea API.

        Returns:
            str: The authentication token.
        """
        now = asyncio.get_event_loop().time()
        if self._access_token and now < self._expires_in - 5:  # refresh 5s early
            return self._access_token

        async with self.session() as session:
            response = await session.post(
                f"{self.base_url}/identity/api/oauth2/token/xpmplatform",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "scope": "xpmheadless",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            if response.status != 200:
                raise await DelineaError.from_response(response)

            data = await response.json()

        token: str | None = data.get("access_token")
        if not token:
            raise ValueError(f"Delinea auth response does not contain a access token. Response: {data}")

        self._access_token = token
        self._expires_in = data.get("expires_in", 60)

        return token

    def get_audit_events_url(
        self, start_date: datetime, page: int | None = None, end_date: datetime | None = None
    ) -> str:
        params = {
            "StartDateTime": start_date.isoformat(),
            "Page": page if page is not None else 1,
            "PageSize": 1000,
            "api-version": "2.0",
            # ordering does not work for some reason but while it is ordered in asc - we do not need it.
            # 'OrderBy': 'eventDateTime'
        }

        if end_date:
            params["EndDateTime"] = end_date.isoformat()

        query_string = urlencode(params)

        return f"{self.base_url}/audit/api/audit-events?{query_string}"

    async def _get_audit_events(
        self, start_date: datetime, page: int | None = None, end_date: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch data from the Delinea API.

        Args:
            start_date: The start date for fetching data.
            end_date: The end date for fetching data.

        Yields:
            dict[str, Any]: The fetched data.
        """
        # https://docs.delinea.com/online-help/platform-api/audit.htm
        auth_token = await self.get_auth_token()
        headers = {"Authorization": f"Bearer {auth_token}"}

        async with self.session() as session:
            response = await session.get(
                self.get_audit_events_url(start_date=start_date, page=page, end_date=end_date),
                headers=headers,
            )

            if response.status != 200:
                raise await DelineaError.from_response(response)

            # example of response:
            # {'auditEvents': [], 'totalCount': 19}
            data: dict[str, Any] = await response.json()

        return data.get("auditEvents", [])

    async def get_audit_events(self, start_date: datetime, end_date: datetime) -> AsyncGenerator[dict[str, Any], None]:
        page = 1
        while True:
            events = await self._get_audit_events(start_date=start_date, end_date=end_date, page=page)
            if not events:
                break

            for event in events:
                yield event

            page += 1

    async def close(self) -> None:  # pragma: no cover
        if self._session:
            await self._session.close()
            self._session = None
