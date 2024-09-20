"""Trellix http client."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, Set

from aiohttp_retry import ExponentialRetry, RetryClient
from aiolimiter import AsyncLimiter
from yarl import URL

from .retry import RetryWithRateLimiter
from .schemas.attributes.edr_affectedhosts import EdrAffectedhostAttributes
from .schemas.attributes.edr_alerts import EdrAlertAttributes
from .schemas.attributes.edr_detections import EdrDetectionAttributes
from .schemas.attributes.edr_threats import EdrThreatAttributes
from .schemas.attributes.epo_events import EpoEventAttributes
from .schemas.token import Scope
from .schemas.trellix_response import TrellixResponse
from .token_refresher import TrellixTokenRefresher


class AuthenticationError(ValueError):
    """Authentication error."""


class TrellixHttpClient(object):
    """Class for Trellix http client."""

    _client: Optional["TrellixHttpClient"] = None
    _session: RetryClient | None = None
    _rate_limiter: AsyncLimiter | None = None
    _rate_limiter_per_day: AsyncLimiter | None = None
    _token_refresher: Optional[TrellixTokenRefresher] = None

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        api_key: str,
        auth_url: str,
        base_url: str,
        rate_limiter: AsyncLimiter | None = None,
        rate_limiter_per_day: AsyncLimiter | None = None,
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
        if rate_limiter_per_day:
            self.set_rate_limiter_per_day(rate_limiter_per_day)

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
    def set_rate_limiter_per_day(cls, rate_limiter: AsyncLimiter) -> None:
        """
        Set rate limiter for the day

        Args:
            rate_limiter:
        """
        cls._rate_limiter_per_day = rate_limiter

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[RetryClient, None]:
        """
        Get configured session with rate limiter.

        Yields:
            AsyncGenerator[RetryClient, None]:
        """
        if cls._session is None:
            cls._session = RetryClient(
                retry_options=RetryWithRateLimiter(
                    ExponentialRetry(attempts=3, start_timeout=5.0, statuses={429}, max_timeout=60.0)
                )
            )

        if cls._rate_limiter and cls._rate_limiter_per_day:
            async with cls._rate_limiter_per_day:
                async with cls._rate_limiter:
                    yield cls._session
        elif cls._rate_limiter:
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
        if self._token_refresher:
            return self._token_refresher

        self._token_refresher = await TrellixTokenRefresher.instance(
            self.client_id, self.client_secret, self.api_key, self.auth_url, scopes
        )

        return self._token_refresher

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

    async def _get_data(self, url: URL, headers: dict[str, str]) -> dict[str, Any]:
        """
        Get data from platform.

        Args:
            url: URL
            headers: dict[str, str]

        Raises:
            Exception: if response status is not 200

        Returns:
            dict[str, Any]:
        """
        async with self.session() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 401:  # pragma: no cover
                    raise AuthenticationError("Unauthorized for request. Refresh token and try again")

                if response.status != 200:
                    raise Exception(
                        "Error while getting data from {0} status {1}: {2}".format(
                            url, response.status, await response.text()
                        ),
                    )

                result: dict[str, Any] = await response.json()

                return result

    def epo_events_url(self, start_date: datetime, limit: int = 10) -> URL:
        """
        Get EPO events url.

        Args:
            start_date: datetime
            limit: int

        Returns:
            URL:
        """
        params = {
            "sort": "timestamp",
            "filter": '{"GT": {"timestamp": "' + start_date.strftime("%Y-%m-%dT%H:%M:%SZ") + '"}}',
            "page[limit]": str(limit),
        }

        return URL("{0}/epo/v2/events".format(self.base_url)).with_query(params)

    def edr_threats_url(self, start_date: datetime, end_date: datetime, limit: int = 10, offset: int = 0) -> URL:
        """
        Get EDR threats url.

        Filter by `from` should be enough to get threats for specified window,
            as it applies on `lastDetected` field.

        It will get all threats from start_date to now.

        Doc:
        https://developer.manage.trellix.com/mvision/apis/threats

        Args:
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            URL:
        """
        params: dict[str, int | str] = {
            "from": int(start_date.timestamp()) * 1000,
            "to": int(end_date.timestamp()) * 1000,
            "page[limit]": str(limit),
            "page[offset]": str(offset),
        }

        return URL("{0}/edr/v2/threats".format(self.base_url)).with_query(params)

    def edr_threat_detections_url(
        self,
        threat_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
        offset: int = 0,
    ) -> URL:
        """
        Get EDR threats url.

        By default, sort is `-rank` (descending).
        We want to use `asc` on firstDetected (ascending) to get the oldest first.

        Filter by `from` should be enough to get threats for specified window,
            as it applies on `lastDetected` field.
        It will get all detection from start_date to now with specified offset and limit.

        Doc:
        https://developer.manage.trellix.com/mvision/apis/threats

        Args:
            threat_id: str
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            URL:
        """
        params: dict[str, int | str] = {
            "sort": "firstDetected",
            "from": int(start_date.timestamp()) * 1000,
            "to": int(end_date.timestamp()) * 1000,
            "page[limit]": str(limit),
            "page[offset]": str(offset),
        }

        return URL("{0}/edr/v2/threats/{1}/detections".format(self.base_url, threat_id)).with_query(params)

    def edr_threat_affectedhosts_url(
        self,
        threat_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
        offset: int = 0,
    ) -> URL:
        """
        Get EDR threats url.

        By default, sort is `-rank` (descending).
        We want to use `asc` on firstDetected (ascending) to get the oldest first.

        Filter by `from` should be enough to get threats for specified window,
            as it applies on `lastDetected` field.
        It will get all detection from start_date to now with specified offset and limit.

        Doc:
        https://developer.manage.trellix.com/mvision/apis/threats

        Args:
            threat_id: str
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            URL:
        """
        params: dict[str, int | str] = {
            "sort": "firstDetected",
            "from": int(start_date.timestamp()) * 1000,
            "to": int(end_date.timestamp()) * 1000,
            "page[limit]": str(limit),
            "page[offset]": str(offset),
        }

        return URL("{0}/edr/v2/threats/{1}/affectedhosts".format(self.base_url, threat_id)).with_query(params)

    def edr_alerts_url(self, start_date: datetime, limit: int = 10) -> URL:
        """
        Get EDR alerts url.

        By default, sort is `-detectionDate` (descending).
        We want to use `asc` (ascending) to get the oldest first.

        Doc:
        https://developer.manage.trellix.com/mvision/apis/threats

        Args:
            start_date: datetime
            limit: int

        Returns:
            URL:
        """
        params: dict[str, int | str] = {
            "sort": "detectionDate",
            "from": int(start_date.timestamp()) * 1000,
            "page[limit]": str(limit),
        }

        return URL("{0}/edr/v2/alerts".format(self.base_url)).with_query(params)

    async def get_epo_events(self, start_date: datetime, limit: int = 10) -> list[TrellixResponse[EpoEventAttributes]]:
        """
        Get EPO events.

        Args:
            start_date: datetime
            limit: int

        Returns:
            list[TrellixResponse[EpoEventAttributes]]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.epo_events_url(start_date, limit)

        try:
            data = await self._get_data(url, headers)
        except AuthenticationError:  # pragma: no cover
            headers = await self._request_headers(Scope.complete_set_of_scopes())
            data = await self._get_data(url, headers)

        return [TrellixResponse[EpoEventAttributes](**result) for result in data["data"]]

    async def get_edr_threats(
        self, start_date: datetime, end_date: datetime, limit: int = 10, offset: int = 0
    ) -> list[TrellixResponse[EdrThreatAttributes]]:
        """
        Get EDR threats.

        Args:
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            Tuple[list[TrellixResponse[EdrThreatAttributes]], bool]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.edr_threats_url(start_date, end_date, limit, offset)

        try:
            data = await self._get_data(url, headers)
        except AuthenticationError:  # pragma: no cover
            headers = await self._request_headers(Scope.complete_set_of_scopes())
            data = await self._get_data(url, headers)

        return [TrellixResponse[EdrThreatAttributes](**result) for result in data["data"]]

    async def get_edr_threat_affectedhosts(
        self, threat_id: str, start_date: datetime, end_date: datetime, limit: int = 10, offset: int = 0
    ) -> list[TrellixResponse[EdrAffectedhostAttributes]]:
        """
        Get EDR threat affected hosts.

        Args:
            threat_id: int
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            list[TrellixResponse[EdrAffectedhostAttributes]]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.edr_threat_affectedhosts_url(threat_id, start_date, end_date, limit, offset)

        try:
            data = await self._get_data(url, headers)
        except AuthenticationError:  # pragma: no cover
            headers = await self._request_headers(Scope.complete_set_of_scopes())
            data = await self._get_data(url, headers)

        return [TrellixResponse[EdrAffectedhostAttributes](**result) for result in data["data"]]

    async def get_edr_threat_detections(
        self,
        threat_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TrellixResponse[EdrDetectionAttributes]]:
        """
        Get EDR threats.

        Args:
            threat_id: int
            start_date: datetime
            end_date: datetime
            limit: int
            offset: int

        Returns:
            list[dict[str, str]]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.edr_threat_detections_url(threat_id, start_date, end_date, limit, offset)

        try:
            data = await self._get_data(url, headers)
        except AuthenticationError:  # pragma: no cover
            headers = await self._request_headers(Scope.complete_set_of_scopes())
            data = await self._get_data(url, headers)

        return [TrellixResponse[EdrDetectionAttributes](**result) for result in data["data"]]

    async def get_edr_alerts(self, start_date: datetime, limit: int = 10) -> list[TrellixResponse[EdrAlertAttributes]]:
        """
        Get EDR threats.

        Args:
            start_date: datetime
            limit: 10

        Returns:
            list[TrellixResponse[EdrAlertAttributes]]:
        """
        headers = await self._request_headers(Scope.complete_set_of_scopes())
        url = self.edr_alerts_url(start_date, limit)

        try:
            data = await self._get_data(url, headers)
        except AuthenticationError:  # pragma: no cover
            headers = await self._request_headers(Scope.complete_set_of_scopes())
            data = await self._get_data(url, headers)

        return [
            TrellixResponse[EdrAlertAttributes](
                **{**result, "attributes": EdrAlertAttributes.parse_response(result.get("attributes"))}
            )
            for result in data["data"]
        ]
