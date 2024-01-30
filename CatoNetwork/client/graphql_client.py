"""Cato graphql client."""

from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, AsyncGenerator

from aiolimiter import AsyncLimiter
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from loguru import logger

from client.schemas.events_feed import EventsFeedQueries, EventsFeedResponseSchema


class CatoRequestType(Enum):
    """Cato request type."""

    ACCOUNT_METRICS = "accountMetrics"
    ACCOUNT_SNAPSHOT = "accountSnapshot"
    AUDIT_FEED = "auditFeed"
    ENTITY_LOOKUP = "entityLookup"
    EVENTS_FEED = "eventsFeed"


class CatoGraphQLClient(object):
    """Class for Cato GraphQL client."""

    _rate_limiters: dict[CatoRequestType, AsyncLimiter] | None = None
    _cato_clients: dict[CatoRequestType, Client] | None = None

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

        self.set_rate_limiter(CatoRequestType.ACCOUNT_METRICS, account_metrics_rate_limiter)
        self.set_rate_limiter(CatoRequestType.ACCOUNT_SNAPSHOT, account_snapshot_rate_limiter)
        self.set_rate_limiter(CatoRequestType.AUDIT_FEED, audit_feed_rate_limiter)
        self.set_rate_limiter(CatoRequestType.ENTITY_LOOKUP, entity_lookup_rate_limiter)
        self.set_rate_limiter(CatoRequestType.EVENTS_FEED, events_feed_rate_limiter)

    @classmethod
    def set_rate_limiter(cls, request_type: CatoRequestType, rate_limiter: AsyncLimiter | None) -> None:
        """
        Set rate limiter for specific request type.

        Args:
            request_type: CatoRequestType
            rate_limiter: AsyncLimiter | None
        """
        if not cls._rate_limiters:
            cls._rate_limiters = {}

        if rate_limiter:
            cls._rate_limiters[request_type] = rate_limiter
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

            cls._rate_limiters[request_type] = _limiter

    @classmethod
    def get_rate_limiter(cls, request_type: CatoRequestType) -> AsyncLimiter:
        """
        Get rate limiter for specific request type.

        Args:
            request_type: CatoRequestType

        Returns:
            AsyncLimiter:
        """
        if not cls._rate_limiters:
            cls._rate_limiters = {}

        _rate_limiter = cls._rate_limiters.get(request_type)

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
            transport = AIOHTTPTransport(url=self.base_url, headers={"x-api-key": self.api_key})

            _cato_client = Client(transport=transport, fetch_schema_from_transport=False)

            self._cato_clients[request_type] = _cato_client

        return _cato_client

    @asynccontextmanager
    async def _session(self, request_type: CatoRequestType) -> AsyncGenerator[Client, None]:
        """
        Get configured GraphQL client with correct rate limiter.

        Args:
            request_type: CatoRequestType

        Yields:
            Client:
        """
        async with self.get_rate_limiter(request_type):
            yield self.cato_client(request_type)

    async def load_events_feed(self, last_event_id: str | None = None) -> EventsFeedResponseSchema:
        """
        Gets data from Cato GraphQL API for events feed.

        Args:
            last_event_id: str | None

        Returns:
            EventsFeedResponseSchema:
        """
        logger.info(f"Loading events feed for account {self.account_id} with marker start from {last_event_id}")
        async with self._session(CatoRequestType.EVENTS_FEED) as session:
            variables = {
                "accountIds": [self.account_id],
                "lastEventId": last_event_id,
            }

            response: dict[str, Any] = await session.execute_async(
                EventsFeedQueries.GET_EVENTS_FEED.value,
                variable_values=variables,
            )

            return EventsFeedResponseSchema(**response.get("eventsFeed", {}))
