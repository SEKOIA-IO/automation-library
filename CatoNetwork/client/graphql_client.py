"""Cato graphql client."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

from aiolimiter import AsyncLimiter
from gql import Client
from gql.client import AsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

from client.schemas.events_feed import EventsFeedQueries, EventsFeedResponseSchema

# gql logs every request and the full response body at INFO level, which would dump customer events to stderr.
logging.getLogger("gql.transport.aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Seconds, applied both to the HTTP request and to the whole GraphQL execution
DEFAULT_TIMEOUT = 60


class CatoRequestType(Enum):
    """Cato request type."""

    ACCOUNT_METRICS = "accountMetrics"
    ACCOUNT_SNAPSHOT = "accountSnapshot"
    AUDIT_FEED = "auditFeed"
    ENTITY_LOOKUP = "entityLookup"
    EVENTS_FEED = "eventsFeed"


class CatoGraphQLClient:
    """Class for Cato GraphQL client."""

    def __init__(
        self,
        api_key: str,
        account_id: str,
        base_url: str | None = None,
        account_metrics_rate_limiter: AsyncLimiter | None = None,
        account_snapshot_rate_limiter: AsyncLimiter | None = None,
        audit_feed_rate_limiter: AsyncLimiter | None = None,
        entity_lookup_rate_limiter: AsyncLimiter | None = None,
        events_feed_rate_limiter: AsyncLimiter | None = None,
    ):
        """
        Initialize CatoGraphQLClient.

        Here is provided limits for different types of requests.
        Default limits are ( ):
            accountMetrics: 120/minute
            accountSnapshot: 120/minute
            auditFeed: 5/minute
            entityLookup: 30/minute
            eventsFeed: 75/minute

        If you want to change limits, you can provide your own AsyncLimiter.

        Args:
            api_key: str
            account_id: str
            base_url: str | None
            account_metrics_rate_limiter: AsyncLimiter | None
            account_snapshot_rate_limiter: AsyncLimiter | None
            audit_feed_rate_limiter: AsyncLimiter | None
            entity_lookup_rate_limiter: AsyncLimiter | None
            events_feed_rate_limiter: AsyncLimiter | None
        """
        self.account_id = account_id
        self.api_key = api_key

        self.base_url = "https://api.catonetworks.com/api/v1/graphql2" if not base_url else base_url

        self._rate_limiters: dict[CatoRequestType, AsyncLimiter] = {}
        self._cato_clients: dict[CatoRequestType, Client] | None = None
        self._sessions: dict[CatoRequestType, AsyncClientSession] = {}

        self.set_rate_limiter(CatoRequestType.ACCOUNT_METRICS, account_metrics_rate_limiter)
        self.set_rate_limiter(CatoRequestType.ACCOUNT_SNAPSHOT, account_snapshot_rate_limiter)
        self.set_rate_limiter(CatoRequestType.AUDIT_FEED, audit_feed_rate_limiter)
        self.set_rate_limiter(CatoRequestType.ENTITY_LOOKUP, entity_lookup_rate_limiter)
        self.set_rate_limiter(CatoRequestType.EVENTS_FEED, events_feed_rate_limiter)

    def set_rate_limiter(self, request_type: CatoRequestType, rate_limiter: AsyncLimiter | None) -> None:
        """
        Set rate limiter for specific request type.

        Args:
            request_type: CatoRequestType
            rate_limiter: AsyncLimiter | None
        """
        if rate_limiter:
            self._rate_limiters[request_type] = rate_limiter
        else:
            match request_type:
                case CatoRequestType.AUDIT_FEED:
                    _limiter = AsyncLimiter(5)

                case CatoRequestType.ENTITY_LOOKUP:
                    _limiter = AsyncLimiter(30)

                case CatoRequestType.EVENTS_FEED:
                    _limiter = AsyncLimiter(75)

                case _:
                    # Default is 120/minute for accountMetrics and accountSnapshot
                    _limiter = AsyncLimiter(120)

            self._rate_limiters[request_type] = _limiter

    def get_rate_limiter(self, request_type: CatoRequestType) -> AsyncLimiter:
        """
        Get rate limiter for specific request type.

        Args:
            request_type: CatoRequestType

        Returns:
            AsyncLimiter:
        """
        _rate_limiter = self._rate_limiters.get(request_type)

        if not _rate_limiter:
            raise ValueError(f"Rate limiter for {request_type} is not set")

        return _rate_limiter

    def cato_client(self, request_type: CatoRequestType) -> Client:
        """
        Get CatoGraphQLClient client.

        Args:
            request_type: CatoRequestType

        Returns:
            Client:
        """
        if not self._cato_clients:
            self._cato_clients = {}

        _cato_client = self._cato_clients.get(request_type)
        if not _cato_client:
            transport = AIOHTTPTransport(
                url=self.base_url,
                headers={"x-api-key": self.api_key},
                ssl=True,
                timeout=DEFAULT_TIMEOUT,
            )

            _cato_client = Client(
                transport=transport,
                fetch_schema_from_transport=False,
                execute_timeout=DEFAULT_TIMEOUT,
            )

            self._cato_clients[request_type] = _cato_client

        return _cato_client

    async def _get_session(self, request_type: CatoRequestType) -> AsyncClientSession:
        """
        Get the connected GraphQL session of a request type, opening it on first use.

        The session (and its aiohttp session) is reused across calls until `close` is called
        or a transport error occurs.

        Args:
            request_type: CatoRequestType

        Returns:
            AsyncClientSession:
        """
        session = self._sessions.get(request_type)
        if session is None:
            session = await self.cato_client(request_type).connect_async()
            self._sessions[request_type] = session

        return session

    async def _close_session(self, request_type: CatoRequestType) -> None:
        """
        Close the GraphQL session of a request type, if any.

        Args:
            request_type: CatoRequestType
        """
        session = self._sessions.pop(request_type, None)
        if session is not None:
            await session.client.close_async()

    async def close(self) -> None:
        """Close every open GraphQL session."""
        for request_type in list(self._sessions):
            await self._close_session(request_type)

    @asynccontextmanager
    async def _session(self, request_type: CatoRequestType) -> AsyncGenerator[AsyncClientSession]:
        """
        Get a connected GraphQL session, under the rate limiter of the request type.

        On any failure but a GraphQL query error, the session is closed so the next call opens a fresh one.

        Args:
            request_type: CatoRequestType

        Yields:
            AsyncClientSession:
        """
        async with self.get_rate_limiter(request_type):
            session = await self._get_session(request_type)
            try:
                yield session
            except TransportQueryError:
                raise
            except BaseException:
                await self._close_session(request_type)
                raise

    async def load_events_feed(self, last_event_id: str | None = None) -> EventsFeedResponseSchema:
        """
        Gets data from Cato GraphQL API for events feed.

        Args:
            last_event_id: str | None

        Returns:
            EventsFeedResponseSchema:
        """
        logger.debug("Loading events feed from marker %s", last_event_id)
        async with self._session(CatoRequestType.EVENTS_FEED) as session:
            variables = {
                "accountIds": [self.account_id],
                "lastEventId": last_event_id,
            }

            response: dict[str, Any] = await session.execute(
                EventsFeedQueries.GET_EVENTS_FEED.value,
                variable_values=variables,
            )

            return EventsFeedResponseSchema(**response.get("eventsFeed", {}))
