import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Iterable

import aiohttp
import orjson
from aiolimiter import AsyncLimiter
from loguru import logger
from pydantic import BaseModel


class GraphAPIError(Exception):
    """Represents a Graph API error (payload serialized as JSON)."""

    @classmethod
    def from_response(cls, payload: Any) -> "GraphAPIError":
        return cls(orjson.dumps(payload).decode("utf-8"))


class PagedResult(BaseModel):
    items: list[dict[str, Any]]
    next_link: str | None = None


class GraphAuditClient:
    """
    Async client for Microsoft Graph audit logs (sign-ins & directory audits).
    Auth: Client Credentials (application permissions).
    Permissions needed: AuditLog.Read.All (admin consent required).

    Docs:
    https://learn.microsoft.com/en-us/graph/api/resources/azure-ad-auditlog-overview?view=graph-rest-1.0
    """

    _session: aiohttp.ClientSession | None = None

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        *,
        api_base_url: str = "https://graph.microsoft.com",
        auth_base_url: str = "https://login.microsoftonline.com",
        rate_limiter: AsyncLimiter | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_base_url = auth_base_url.rstrip("/")

        # Token cache
        self._token: str | None = None
        self._token_expires_at: float = 0.0  # event-loop time in seconds

        # Rate limiter (defaults to 25 req/sec)
        self._rate_limiter = rate_limiter or AsyncLimiter(25, 1)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._token = None
        self._token_expires_at = 0.0

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        async with self._rate_limiter:
            yield self._session

    async def _ensure_token(self) -> str:
        """
        Docs:
        https://learn.microsoft.com/en-us/graph/auth/auth-concepts

        Obtain bearer token:
        https://learn.microsoft.com/en-us/graph/auth-v2-service?tabs=http

        Returns:
            str:
        """
        now = asyncio.get_event_loop().time()
        if self._token and now < self._token_expires_at - 60:  # refresh 60s early
            return self._token

        token_url = f"{self.auth_base_url}/{self.tenant_id}/oauth2/v2.0/token"
        form = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }

        async with self.session() as s:
            async with s.post(token_url, data=form) as resp:
                text = await resp.text()
                if resp.status != 200:
                    logger.error("Token error {0}: {1}", resp.status, text)

                    raise GraphAPIError.from_response(text)

                data = orjson.loads(text)
                token: str | None = data.get("access_token")
                if not token:
                    raise GraphAPIError("No access_token in token response")

                self._token = token

                # usually 3600 but based on docs in example it is 3599
                self._token_expires_at = now + int(data.get("expires_in", 3599))

                return token

    async def _get_paged_result(self, url: str) -> PagedResult:
        backoff = 1.0
        for attempt in range(3):  # simple exponential backoff
            token = await self._ensure_token()

            async with self.session() as session:
                headers = {"Authorization": f"Bearer {token}"}

                async with session.get(url, headers=headers) as resp:
                    text = await resp.text()

                    # Unauthorized: try once to refresh token
                    if resp.status == 401 and attempt == 0:
                        self._token = None
                        await self._ensure_token()
                        continue

                    # Throttled: respect Retry-After if present
                    if resp.status == 429:
                        delay = float(resp.headers.get("Retry-After", backoff))
                        await asyncio.sleep(delay)
                        backoff *= 2

                        continue

                    # Retry on transient server errors
                    if 500 <= resp.status < 600:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                    if resp.status != 200:
                        logger.error("Graph error {0}: {1}", resp.status, text)
                        raise GraphAPIError.from_response(text)

                    body = orjson.loads(text)

                    return PagedResult(
                        items=body.get("value", []),
                        next_link=body.get("@odata.nextLink"),
                    )

        raise GraphAPIError("Exceeded retries for Graph request")

    @staticmethod
    def _format_datetime(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _build_filter(
        self, field: str, start: datetime | None, end: datetime | None, extra: Iterable[str] = ()
    ) -> str:
        parts: list[str] = []
        if start:
            parts.append(f"{field} ge {self._format_datetime(start)}")

        if end:
            parts.append(f"{field} le {self._format_datetime(end)}")

        parts.extend(extra)

        return " and ".join(parts) if parts else ""

    def list_signins_url(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> str:
        base = f"{self.api_base_url}/v1.0/auditLogs/signIns"
        build_filter = self._build_filter("createdDateTime", start, end, extra_filter)
        params: list[str] = [
            item
            for item in [
                f"$top={top}" if top else None,
                f"$filter={build_filter}" if build_filter else None,
                f"$select={','.join(select)}" if select else None,
                f"$orderby={orderby}" if orderby else None,
            ]
            if item is not None
        ]

        return base + ("?" + "&".join(params) if params else "")

    async def _list_signins(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        next_link: str | None = None,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> PagedResult:
        url = next_link
        if url is None:
            url = self.list_signins_url(
                start=start, end=end, extra_filter=extra_filter, top=top, select=select, orderby=orderby
            )

        return await self._get_paged_result(url)

    async def list_signins(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetch ALL sign-in logs for the window (follows @odata.nextLink).

        Docs:
        https://learn.microsoft.com/en-us/graph/api/signin-list?view=graph-rest-1.0&tabs=http
        """
        first = await self._list_signins(
            start=start, end=end, top=top, extra_filter=extra_filter, select=select, orderby=orderby
        )

        next_link = first.next_link
        for item in first.items:
            yield item

        while next_link:
            page = await self._list_signins(next_link=next_link)
            for item in page.items:
                yield item

            next_link = page.next_link

        return

    def list_directory_audits_url(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> str:
        base = f"{self.api_base_url}/v1.0/auditLogs/directoryAudits"
        build_filter = self._build_filter("activityDateTime", start, end, extra_filter)

        params: list[str] = [
            item
            for item in [
                f"$top={top}" if top else None,
                f"$filter={build_filter}" if build_filter else None,
                f"$select={','.join(select)}" if select else None,
                f"$orderby={orderby}" if orderby else None,
            ]
            if item is not None
        ]

        return base + ("?" + "&".join(params) if params else "")

    async def _list_directory_audits_page(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        next_link: str | None = None,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> PagedResult:
        """Fetch ONE page of directory audit logs (use next_link to continue)."""
        url = next_link
        if url is None:
            url = self.list_directory_audits_url(start, end, top, extra_filter, select, orderby)

        return await self._get_paged_result(url)

    async def list_directory_audits(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        top: int = 1000,
        extra_filter: Iterable[str] = (),
        select: Iterable[str] = (),
        orderby: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch ALL directory audit logs for the window (follows @odata.nextLink)."""
        first = await self._list_directory_audits_page(
            start=start, end=end, top=top, extra_filter=extra_filter, select=select, orderby=orderby
        )

        for item in first.items:
            yield item

        next_link = first.next_link
        while next_link:
            page = await self._list_directory_audits_page(next_link=next_link)
            for item in page.items:
                yield item

            next_link = page.next_link

        return
