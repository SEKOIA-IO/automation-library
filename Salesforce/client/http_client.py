"""Salesforce http client."""
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Tuple
from urllib.parse import urlencode

import aiocsv
import aiofiles
from aiohttp import ClientResponse, ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger
from yarl import URL

from .schemas.log_file import SalesforceEventLogFilesResponse
from .token_refresher import SalesforceTokenRefresher


class SalesforceHttpClient(object):
    """Class for Salesforce Http client."""

    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        rate_limiter: AsyncLimiter | None = None,
    ):
        """
        Initialize SalesforceHttpClient.

        Args:
            client_id: str
            client_secret: str
            base_url: str
            rate_limiter: AsyncLimiter
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url

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

    async def _get_token_refresher(self) -> SalesforceTokenRefresher:
        """
        Get token refresher.

        Returns:
            SalesforceTokenRefresher:
        """
        return await SalesforceTokenRefresher.instance(
            self.client_id,
            self.client_secret,
            self.base_url,
        )

    @classmethod
    def _query_to_http_param(cls, query: str) -> str:
        """
        Convert query to http param with additional formatting.

        Args:
            query: str

        Returns:
            str:
        """
        return " ".join([line.strip() for line in query.strip().splitlines()]).replace(" ", "+").replace(",", "+,")

    @staticmethod
    def _log_files_query(start_from: str | None) -> str:
        """
        Query to get log files.

        Docs for query with CreatedDate filter
        https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/event_log_file_hourly_overview.htm

        Value of filter criterion for field 'CreatedDate' must be of type dateTime and should not be enclosed in quotes.

        Args:
            start_from: str | None

        Returns:
            str:
        """
        date_filter = "AND CreatedDate > {0}".format(start_from) if start_from else ""

        return """
            SELECT Id, EventType, LogFile, LogDate, LogFileLength
                FROM EventLogFile WHERE Interval = \'Hourly\' {0}
        """.format(
            date_filter
        )

    def _request_url_with_query(self, query: str) -> URL:
        """
        Creates request url to perform query operation.

        Include query formatting and correct encoding.

        Args:
            query: str

        Returns:
            URL:
        """
        params = {
            "q": self._query_to_http_param(query),
        }

        return URL("{0}/services/data/v58.0/query".format(self.base_url)).with_query(
            urlencode(params, safe=">+,'=:", encoding="utf-8")
        )

    async def _request_headers(self) -> Dict[str, str]:
        """
        Get request headers with auth.

        Returns:
            Dict[str, str]:
        """
        token_refresher = await self._get_token_refresher()

        async with token_refresher.with_access_token() as token:
            headers = {
                "Authorization": "Bearer {0}".format(token.token.access_token),
                "Content-Type": "application/json",
            }

        return headers

    @classmethod
    async def _handle_error_response(cls, response: ClientResponse) -> None:
        """
        Handle error response.

        Args:
            response: ClientResponse

        Raises:
            Exception: in case if response status is not 200
        """
        if response.status != 200:
            error_response = await response.json()
            error_msg = ",".join(["Error {errorCode}: {message}".format(**error) for error in error_response])

            raise Exception(error_msg)

    async def get_log_files(self, start_from: str | None = None) -> SalesforceEventLogFilesResponse:
        """

        Args:
            start_from: str

        Raises:
            ValueError: Salesforce response cannot be processed

        Returns:
            SalesforceEventLogFilesResponse:
        """
        logger.info("Getting log files from Salesforce. Start date is {0}", start_from)

        query = self._log_files_query(start_from)

        url = self._request_url_with_query(query)
        headers = await self._request_headers()

        async with self.session() as session:
            response = await session.get(url, headers=headers, json={})
            await self._handle_error_response(response)

            result = SalesforceEventLogFilesResponse(**await response.json())
            if not result.done:
                raise ValueError("Salesforce response is not done")

        return result

    async def get_log_file_content(
        self,
        log_file_uri: str,
        size_to_process: int = 1024 * 1024,
        chunk_size: int = 1024,
        temp_dir: str | None = None,
        persist_to_file: bool | None = None,
    ) -> Tuple[list[dict[str, Any]] | None, str | None]:
        """
        Get log file content.

        Api docs:
        https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_sobject_blob_retrieve.htm
        https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_event_log_file_blob.htm

            Persists response into local file or return response body as dict. If persist_to_file is None, then check
        response content-length and if it is greater than `size_to_process`, then persist to file, otherwise
        return parsed data.

            Left part of tuple is data as dict, right part is filepath on local machine.

        Args:
            log_file_uri: str
            size_to_process: int
            chunk_size: int
            temp_dir: str | None
            persist_to_file: bool | None

        Returns:
            Tuple[str, str]:
        """
        headers = await self._request_headers()
        url = "{0}{1}".format(self.base_url, log_file_uri)

        async with self.session() as session:
            async with session.get(url, headers=headers) as response:
                content_length = int(response.headers.get("Content-Length", 0))

                save_to_file = persist_to_file if persist_to_file is not None else content_length > size_to_process

                await self._handle_error_response(response)

                if save_to_file:
                    async with aiofiles.tempfile.NamedTemporaryFile("wb", delete=False, dir=temp_dir) as file:
                        while True:
                            chunk = await response.content.read(chunk_size)
                            if not chunk:
                                break
                            await file.write(chunk)

                        return None, file.name
                else:
                    result = []
                    async for row in aiocsv.AsyncDictReader(response.content, delimiter=","):
                        result.append(row)

                    return result, None
