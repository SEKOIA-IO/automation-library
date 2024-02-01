"""Salesforce http client."""

import csv
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Tuple
from urllib.parse import urlencode

from aiohttp import ClientResponse, ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger
from sekoia_automation.aio.helpers.http.utils import save_aiohttp_response
from yarl import URL

from .schemas.log_file import EventLogFile, SalesforceEventLogFilesResponse
from .token_refresher import SalesforceTokenRefresher


class LimiterType(Enum):
    DEFAULT = 0
    DAILY = 1
    HOURLY_MANAGED = 2


class SalesforceHttpClient(object):
    """Class for Salesforce Http client."""

    _sessions: dict[str, ClientSession] = {}
    _rate_limiters: dict[str, AsyncLimiter] = {}
    _daily_rate_limiters: dict[str, AsyncLimiter] = {}
    _hourly_managed_content_public_limiters: dict[str, AsyncLimiter] = {}

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
        self.connector_uuid = self.get_unique_client_key(client_id, client_secret)

        if rate_limiter:
            self.set_rate_limiter(self.connector_uuid, rate_limiter, LimiterType.DEFAULT)

    @classmethod
    def get_unique_client_key(cls, client_id: str, client_secret: str) -> str:
        return "{0}{1}".format(client_id, client_secret)

    @classmethod
    def set_rate_limiter(cls, client_uuid: str, rate_limiter: AsyncLimiter, limiter_type: LimiterType) -> None:
        """
        Set rate limiter.

        Args:
            client_uuid: str
            rate_limiter: AsyncLimiter
            limiter_type: LimiterType
        """
        match limiter_type:
            case LimiterType.DAILY:
                cls._daily_rate_limiters[client_uuid] = rate_limiter
                return

            case LimiterType.HOURLY_MANAGED:
                cls._hourly_managed_content_public_limiters[client_uuid] = rate_limiter
                return

            case _:
                cls._rate_limiters[client_uuid] = rate_limiter
                return

    @classmethod
    @asynccontextmanager
    async def session(cls, client_uuid: str) -> AsyncGenerator[ClientSession, None]:
        """
        Get configured session with rate limiter.

        Args:
            client_uuid: str

        Returns:
            AsyncGenerator[ClientSession, None]:
        """
        if cls._sessions.get(client_uuid) is None:
            cls._sessions[client_uuid] = ClientSession(headers={"Accept-Encoding": "gzip"}, auto_decompress=True)

        default_limiter = cls._rate_limiters.get(client_uuid)
        daily_rate_limiter = cls._daily_rate_limiters.get(client_uuid)
        hourly_managed_limiter = cls._hourly_managed_content_public_limiters.get(client_uuid)

        if default_limiter:
            async with default_limiter:
                if hourly_managed_limiter and daily_rate_limiter:
                    async with daily_rate_limiter, hourly_managed_limiter:
                        yield cls._sessions[client_uuid]

                elif hourly_managed_limiter:
                    async with hourly_managed_limiter:
                        yield cls._sessions[client_uuid]

                elif daily_rate_limiter:
                    async with daily_rate_limiter:
                        yield cls._sessions[client_uuid]

                else:
                    yield cls._sessions[client_uuid]
        else:
            yield cls._sessions[client_uuid]

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
    def _log_files_query(start_from: datetime | None = None) -> str:
        """
        Query to get log files.

        Docs for query with CreatedDate filter
        https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/event_log_file_hourly_overview.htm

        Value of filter criterion for field 'CreatedDate' must be of type dateTime and should not be enclosed in quotes.

        Args:
            start_from: datetime | None

        Returns:
            str:
        """
        date_filter = "AND CreatedDate > {0}".format(start_from.strftime("%Y-%m-%dT%H:%M:%SZ")) if start_from else ""

        return """
            SELECT Id, EventType, LogFile, LogDate, CreatedDate, LogFileLength
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
                "Content-Encoding": "gzip",
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
            try:
                error_response = await response.json()
            except Exception:
                error_msg = await response.text()

                raise Exception(error_msg)

            error_msg = ",".join(["Error {errorCode}: {message}".format(**error) for error in error_response])

            raise Exception(error_msg)

    async def update_limiters(self) -> None:
        """Updates dynamically limits."""

        headers = await self._request_headers()
        request_url = URL("{0}/services/data/v60.0/limits/".format(self.base_url))
        logger.info("Try to get salesforce limits")

        client_uuid = self.get_unique_client_key(self.client_id, self.client_secret)

        # try:
        async with (self.session(client_uuid) as session):
            async with session.get(request_url, headers=headers, json={}) as response:
                await self._handle_error_response(response)

                result = await response.json()

                daily_requests: int | None = result.get("DailyApiRequests", {}).get("Max")
                logger.info("Found limits for DailyApiRequests {0}".format(daily_requests))
                if daily_requests is not None:
                    self.set_rate_limiter(client_uuid, AsyncLimiter(daily_requests, 60 * 60 * 24), LimiterType.DAILY)

                hourly_managed_content_public_requests: int | None = result.get(
                    "HourlyManagedContentPublicRequests", {}
                ).get("Max")
                logger.info(
                    "Found limits for HourlyManagedContentPublicRequests {0}".format(
                        hourly_managed_content_public_requests
                    )
                )
                if hourly_managed_content_public_requests is not None:
                    self.set_rate_limiter(
                        client_uuid,
                        AsyncLimiter(hourly_managed_content_public_requests, 60 * 60),
                        LimiterType.HOURLY_MANAGED,
                    )
        # except Exception:
        #     logger.info("Cannot update daily and hourly limits for connector")

    async def get_log_files(self, start_from: datetime | None = None) -> SalesforceEventLogFilesResponse:
        """
        Get log files from Salesforce.

        Args:
            start_from: datetime | None

        Raises:
            ValueError: Salesforce response cannot be processed

        Returns:
            SalesforceEventLogFilesResponse:
        """
        logger.info("Getting log files from Salesforce. Start date is {0}", start_from)

        query = self._log_files_query(start_from)

        url = self._request_url_with_query(query)
        headers = await self._request_headers()
        client_uuid = self.get_unique_client_key(self.client_id, self.client_secret)

        async with self.session(client_uuid) as session:
            async with session.get(url, headers=headers, json={}) as response:
                await self._handle_error_response(response)

                result = SalesforceEventLogFilesResponse(**await response.json())
                if not result.done:
                    raise ValueError("Salesforce response is not done")

        logger.info("Got {0} log files from Salesforce. Start date is {1}", len(result.records), start_from)

        return result

    async def get_log_file_content(
        self,
        log_file: EventLogFile,
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
            log_file: EventLogFile
            size_to_process: int
            chunk_size: int
            temp_dir: str | None
            persist_to_file: bool | None

        Returns:
            Tuple[str, str]:
        """
        headers = await self._request_headers()
        url = "{0}{1}".format(self.base_url, log_file.LogFile)
        _tmp_dir = temp_dir if temp_dir is not None else "/tmp"
        client_uuid = self.get_unique_client_key(self.client_id, self.client_secret)

        logger.info("Start to process log file from Salesforce. Log file is {0}", log_file.Id)

        async with self.session(client_uuid) as session:
            async with session.get(url, headers=headers) as response:
                await self._handle_error_response(response)

                content_length = int(log_file.LogFileLength)

                logger.info(
                    """
                        Log file info:
                         logfile Id: {file_id}
                         logfile Url: {url}
                         content length: {content_length}
                         maximum log file size to process in memory: {size_to_process}
                         chunk size: {chunk_size}
                         always persist to file: {persist_to_file}
                     """,
                    file_id=log_file.Id,
                    url=log_file.LogFile,
                    content_length=content_length,
                    size_to_process=size_to_process,
                    chunk_size=chunk_size,
                    persist_to_file=persist_to_file,
                )

                save_to_file = persist_to_file if persist_to_file is not None else content_length > size_to_process

                if save_to_file:
                    logger.info("Persist log file {0} to local file", log_file.Id)

                    file_name = await save_aiohttp_response(response, chunk_size=chunk_size, temp_dir=_tmp_dir)

                    return None, file_name
                else:
                    logger.info("Get log file content in memory {0}", log_file.Id)

                    data = await response.text()

                    return list(csv.DictReader(data.splitlines(), delimiter=",")), None
