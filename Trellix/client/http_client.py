"""Trellix http client."""
import asyncio
from datetime import datetime, timedelta
from typing import List, Set

from aiohttp import ClientSession

from .schemas.attributes.investigations import InvestigationAttributes
from .schemas.attributes.searches import SearchHistoricalAttributes, SearchRealtimeAttributes
from .schemas.edr import TrellixEdrResponse
from .schemas.token import Scope
from .token_refresher import TrellixTokenRefresher


class TrellixHttpClient(object):
    """Class for Trellix http client."""

    _session: ClientSession | None = None

    def __init__(self, client_id: str, client_secret: str, api_key: str, auth_url: str, base_url: str):
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

    @classmethod
    def session(cls) -> ClientSession:
        """Get session."""
        if cls._session is None:
            cls._session = ClientSession()

        return cls._session

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

    @property
    def _edr_historical_searches_query_url(self) -> str:
        """
        Get request url for historical searches query.

        Returns:
            str:
        """
        return "{0}/edr/v2/searches/historical".format(self.base_url)

    @property
    def _edr_investigations_url(self) -> str:
        """
        Get request url for investigations result.

        Returns:
            str:
        """
        return "{0}/edr/v2/investigations".format(self.base_url)

    def _edr_historical_searches_result_url(self, search_id: str) -> str:
        """
        Get request url for historical searches result.

        Returns:
            str:
        """
        return "{0}/edr/v2/searches/historical/{1}/results".format(self.base_url, search_id)

    @property
    def _edr_realtime_searches_query_url(self) -> str:
        """
        Get request url for historical searches query.

        Returns:
            str:
        """
        return "{0}/edr/v2/searches/realtime".format(self.base_url)

    def _edr_realtime_searches_result_url(self, search_id: str) -> str:
        """
        Get request url for historical searches result.

        Returns:
            str:
        """
        return "{0}/edr/v2/searches/realtime/{1}/results".format(self.base_url, search_id)

    def _edr_searches_job_status_url(self, search_id: str) -> str:
        """
        Get request url for historical searches job status.

        Will return one of:
            Status code 200 — The search is still in progress. Retry after 15 seconds.
            Status code 303 — The search is finished. You can proceed to get results.

        Delay between requests should be 15 seconds.

        Returns:
            str:
        """
        return "{0}/edr/v2/searches/queue-jobs/{1}".format(self.base_url, search_id)

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

    async def _wait_for_search(self, search_id: str, scopes: Set[Scope]) -> None:
        """
        Wait for search to be finished.

        Args:
            search_id: str
            scopes: Set[Scope]
        """
        search_status_url = self._edr_searches_job_status_url(search_id)
        while True:
            headers = self._request_headers(scopes)
            async with self.session().get(search_status_url, headers=headers) as status_response:
                if status_response.status == 303:
                    break

                # In documentation it is said that we should wait 15 seconds before next request
                await asyncio.sleep(15)

    async def get_edr_historical_searches(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> List[TrellixEdrResponse[SearchHistoricalAttributes]]:
        """
        All necessary workflow to get historical searches.

        Documentation for more details:
            https://docs.trellix.com/fr/bundle/mvision-endpoint-detection-and-response-product-guide/page/GUID-1769457E-C7E4-4186-ABFE-54AFB1A28ECE.html

        Returns:
            List[TrellixEdrResponse[SearchHistoricalAttributes]]:
        """
        query_url = self._edr_historical_searches_query_url
        scopes = Scope.set_for_historical_searches()

        headers = await self._request_headers(scopes)

        _start_time = (
            start_time
            if start_time is not None
            else datetime.utcnow() - timedelta(days=15)
        )

        _end_time = end_time if end_time is not None else datetime.utcnow()

        # TODO check attributes once it have any data
        query_body = {
            "data": {
                "type": "historicalSearches",
                "attributes": {"startTime": _start_time.isoformat(), "endTime": _end_time.isoformat()},
            }
        }

        async with self.session().post(query_url, headers=headers, data=query_body) as search_response:
            search_id = (await search_response.json())["data"]["id"]
            await self._wait_for_search(search_id, scopes)

        headers = await self._request_headers(scopes, encoding=False)
        results_url = self._edr_historical_searches_result_url(search_id)
        async with self.session().get(results_url, headers=headers) as results_response:
            data = await results_response.json()

        return [TrellixEdrResponse[SearchHistoricalAttributes](**result) for result in data["data"]]

    async def get_edr_realtime_searches(self) -> List[TrellixEdrResponse[SearchRealtimeAttributes]]:
        """
        All necessary workflow to get realtime searches.

        Documentation for more details:
            https://docs.trellix.com/fr/bundle/mvision-endpoint-detection-and-response-product-guide/page/GUID-D08D9CF3-45E5-4EB2-A155-A618730BDA46.html#GUID-D08D9CF3-45E5-4EB2-A155-A618730BDA46

        Returns:
            List[TrellixEdrResponse[SearchRealtimeAttributes]]:
        """
        query_url = self._edr_realtime_searches_query_url
        scopes = Scope.set_for_realtime_searches()

        headers = await self._request_headers(scopes)

        # TODO check attributes once it have any data
        query_body = {"data": {"type": "realtimeSearches", "attributes": {"query": "HostInfo"}}}

        async with self.session().post(query_url, headers=headers, data=query_body) as search_response:
            search_id = (await search_response.json())["data"]["id"]
            await self._wait_for_search(search_id, scopes)

        headers = await self._request_headers(scopes, encoding=False)
        results_url = self._edr_realtime_searches_result_url(search_id)
        async with self.session().get(results_url, headers=headers) as results_response:
            data = await results_response.json()

        return [TrellixEdrResponse[SearchRealtimeAttributes](**result) for result in data["data"]]

    async def get_edr_investigations(self) -> List[TrellixEdrResponse[InvestigationAttributes]]:
        """
        All necessary workflow to get realtime searches.

        Documentation for more details:
            https://docs.trellix.com/fr/bundle/mvision-endpoint-detection-and-response-product-guide/page/GUID-7C6805BA-E8C4-45E8-A5B7-C2F7BD6B06AC.html

        Returns:
            List[TrellixEdrResponse[InvestigationAttributes]]:
        """
        investigations_url = self._edr_investigations_url
        scopes = Scope.set_for_investigations()

        headers = await self._request_headers(scopes)
        # TODO: Add logic to go through all pages once data is available
        async with self.session().get(investigations_url, headers=headers) as results_response:
            data = await results_response.json()

        return [TrellixEdrResponse[InvestigationAttributes](**result) for result in data["data"]]
