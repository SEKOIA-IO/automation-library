from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Awaitable, Callable

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger

from nozomi_networks.client.errors import NozomiAuthError, NozomiError
from nozomi_networks.client.event_type import EventType


class NozomiClient(object):
    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None
    _rate_limiter_second: AsyncLimiter | None = None

    def __init__(
        self,
        key_name: str,
        key_token: str,
        base_url: str = "https://vantagetechalliancesinstance.customers.us1.vantage.nozominetworks.io",
    ) -> None:
        """
        Initialize the NozomiClient with the provided credentials and base URL.

        Args:
            key_name: The name of the Nozomi API key.
            key_token: The token of the Nozomi API key.
            base_url: The base URL for the Nozomi Vantage API.
        """
        self.key_name = key_name
        self.key_token = key_token
        self.base_url = base_url
        self._authorization: str | None = None

        self._rate_limiter = AsyncLimiter(max_rate=60, time_period=60)  # 60 requests per minute

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[ClientSession, None]:
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
        else:  # pragma: no cover
            yield self._session

    async def refresh_authorization(self) -> None:
        """
        Fetch the authentication token from the Nozomi API.

        Returns:
            str: The authentication token.
        """
        async with self.session() as session:
            response = await session.post(
                f"{self.base_url}/api/v1/keys/sign_in",
                data={"key_name": self.key_name, "key_token": self.key_token},
            )

            if response.status != 200:
                raise await NozomiError.from_response(response)

            headers = response.headers
            self._authorization = headers.get("authorization")

            if self._authorization is None:
                logger.error("Authorization header not found in response.")

                raise NozomiAuthError("Authorization header not found in response.")

    async def _retry(self, func: Callable[[int], Awaitable[dict[str, Any]]], page: int) -> dict[str, Any]:
        """
        Call a function that retries on error.

        Args:
            func: A callable that takes the base URL and returns a dictionary.

        Returns:
            dict[str, Any]: The result of the function call.
        """
        try:
            return await func(page)
        except NozomiError:
            # If authentication fails, fetch a new token and retry
            await self.refresh_authorization()

            return await func(page)

    async def fetch_events(self, event_type: EventType, start_date: datetime) -> AsyncGenerator[dict[str, Any], None]:
        """
        Generator function is used to fetch events from the Nozomi API starting from a specific date.

        This function yields event along with its page number.

        Args:
            event_type:
            start_date:
        """

        async def _fetch(page: int) -> dict[str, Any]:
            if self._authorization is None:
                await self.refresh_authorization()

            auth = self._authorization
            if not auth:
                raise NozomiAuthError("Authorization can not be set during request.")

            async with self.session() as session:
                headers = {"Authorization": self._authorization}

                params = {
                    "page": page,
                    "size": 100,  # Adjust size as needed
                    **self._get_filters(event_type, start_date),
                }

                response = await session.get(
                    f"{self.base_url}/api/v1/{event_type.value}",
                    headers=headers,
                    params=params,
                )

                logger.info(f"Got response {response.status} for event type {event_type} and query params: {params}")

                if response.status != 200:
                    raise await NozomiError.from_response(response)

                response_data: dict[str, Any] | None = await response.json()
                if not response_data:
                    raise NozomiError(400, "No data returned from Nozomi API.")

                return response_data

        # Start fetching events always from page 1
        request_page = 1
        events_count = 0

        while True:
            result = await self._retry(_fetch, request_page)
            data = result.get("data", [])
            total_count = result.get("meta", {}).get("count")

            if not data:
                return

            for event in data:
                events_count += 1
                yield event

            if total_count is not None and events_count >= int(total_count):
                logger.info(
                    f"Total events fetched: {events_count}. "
                    f"Expected total count in run is {total_count} for event type {event_type}."
                )

                # If we have fetched all events, we can stop
                return

            request_page += 1

    @staticmethod
    def _get_filters(event_type: EventType, start_date: datetime) -> dict[str, Any]:
        """
        Formats the filters for the Nozomi API request and create query params.

        Args:
            event_type:
            start_date:

        Returns:
            dict[str, Any]:
        """
        match event_type:
            case EventType.Assets:
                # Filter by `created_time` field and it should be in ISO 8601 format. But it does not work
                # So convert to unix timestamp in milliseconds
                return {
                    "filter[record_created_at][gt]": int(start_date.timestamp() * 1000),
                    "sort[record_created_at]": "asc",
                }

            case EventType.Alerts:
                # Filter by `record_created_at` field and it should be in ISO 8601 format regarding specification.
                # But it does not work with `created_time` field.
                return {
                    "filter[record_created_at][gt]": int(start_date.timestamp() * 1000),
                    "sort[record_created_at]": "asc",
                }
            case EventType.Vulnerabilities:
                # We should filter by the time and it is in unix timestamp format.
                # It does not work with any `creation_time` field in any format
                return {
                    "filter[time][gt]": int(start_date.timestamp() * 1000),  # Convert to milliseconds
                    "sort[time]": "asc",
                }

            case EventType.WirelessNetworks:
                # Filter by `created_at` field and it should be in time format.
                # When try to deal with `record_created_at` it returns 400 Bad Request.
                return {
                    "filter[created_at][gt]": int(start_date.timestamp() * 1000),
                    "sort[created_at]": "desc",
                }

        return {}

    async def close(self) -> None:  # pragma: no cover
        """
        Close the Nozomi client session.

        This method should be called when the client is no longer needed to release resources.
        """
        if self._session:
            await self._session.close()
            self._session = None
            self._rate_limiter = None
