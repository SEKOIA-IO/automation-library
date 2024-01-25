"""Contains BroadcomCloudSwgClient."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from itertools import groupby
from typing import Any, AsyncGenerator, Tuple

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger
from sekoia_automation.aio.helpers.http.utils import save_aiohttp_response
from yarl import URL


class BroadcomCloudSwgClient(object):
    """BroadcomCloudSwgClient."""

    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    _time_format = "%H:%M:%S"
    _date_format = "%Y-%m-%d"

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str | None = None,
        rate_limiter: AsyncLimiter | None = None,
    ) -> None:
        """
        Initialize BroadcomCloudSwgClient.

        Args:
            username: str
            password: str
        """
        self.username = username
        self.password = password
        self.base_url = base_url or "https://portal.threatpulse.com"
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

        Yields:
            AsyncGenerator[ClientSession, None]:
        """
        if cls._session is None:
            cls._session = ClientSession(
                conn_timeout=None,
                read_timeout=None,
                timeout=None,
                headers={"Accept-Encoding": "gzip"},
                auto_decompress=True,
            )

        if cls._rate_limiter:
            async with cls._rate_limiter:
                yield cls._session
        else:
            yield cls._session

    def get_real_time_log_data_url(
        self,
        start_date: datetime,
        end_date: datetime,
        token: str | None = None,
        max_mb: int = 100,
    ) -> URL:
        """
        Creates url to fetch reports.

        Notes:
            * Timestamp should be in milliseconds that is why we perform * 1000.
            * date fields should be in utc zone
            * token is required to be present in url, but might have "none" string value
            * max_mb cannot be higher than 512 according docs. If it is > 512 api will use 512 as max value

        Docs:
        https://techdocs.broadcom.com/us/en/symantec-security-software/web-and-network-security/cloud-swg/help/cloudswg-api-reference/report-sync-about.html
        https://techdocs.broadcom.com/us/en/symantec-security-software/web-and-network-security/cloud-swg/help/cloudswg-api-reference/report-sync-about/report-sync-api.html#topic.dita_4509cfa5-a73d-4ebc-8a12-9e398dc2e8f5_section_5

        Args:
            start_date: datetime
            end_date: datetime
            token: str | None
            max_mb: int

        Returns:
            URL:
        """
        params: dict[str, int | str] = {
            "endDate": int(end_date.timestamp()) * 1000,
            "startDate": int(start_date.timestamp()) * 1000,
            "maxMB": max_mb,
            "token": (token or "none"),
        }

        return URL("{0}/reportpod/logs/sync".format(self.base_url)).with_query(params)

    async def get_report_sync(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        token: str | None = None,
    ) -> Tuple[bool, str | None, str]:
        """
        Get report as zipped file.

        Along with file_path this function also produce token from header
        and boolean result that determines if we should continue processing.

        Docs:
        https://techdocs.broadcom.com/us/en/symantec-security-software/web-and-network-security/cloud-swg/help/cloudswg-api-reference/report-sync-about/report-sync-api.html

        Args:
            start_date: datetime | None
            end_date: datetime | None
            token: str | None

        Returns:
            Tuple[bool, str | None, str]
        """
        headers = {
            "X-APIUsername": self.username,
            "X-APIPassword": self.password,
            "Content-Encoding": "gzip",
        }

        _start_date = start_date or datetime.utcnow() - timedelta(days=30)
        _end_date = end_date or datetime.utcnow()

        url = self.get_real_time_log_data_url(start_date=_start_date, end_date=_end_date, token=token)

        async with self.session() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError("Cannot get data. Status code is {0}".format(response.status))

                response_headers = response.headers
                logger.info("Response from Broadcom have 200 status. Start to save log files archive.")

                file_name = await save_aiohttp_response(response)

                logger.info("Log files archive has been saved.")

                more_data_is_available = response_headers.get("X-sync-status", "done") == "more"
                response_token = response_headers.get("X-sync-token")

                return more_data_is_available, response_token, file_name

    @classmethod
    def parse_input_string(cls, value: str, fields: list[str] | None = None) -> dict[str, str]:
        """
        Parse line string and returns a dict representation.

        Doc:
        https://techdocs.broadcom.com/us/en/symantec-security-software/web-and-network-security/cloud-swg/help/wss-reference/accesslogformats-ref.html

        Args:
            value: str
            fields: list[str] | None

        Returns:
            dict[str, str]
        """
        _fields = fields or cls.full_list_of_elff_fields()
        _str_to_work = value.rstrip("\n")
        _values = []

        delimiter = " "
        while len(_str_to_work) > 1:
            try:
                end_index = _str_to_work.index(delimiter)
            except ValueError:
                end_index = len(_str_to_work)

            if end_index == 0:
                _str_to_work = _str_to_work[1:]

                continue

            _field_value = _str_to_work[0:end_index]
            _str_to_work = _str_to_work[end_index + 1 :]

            if _str_to_work.startswith('"'):
                delimiter = '" '
            else:
                delimiter = " "

            if _field_value.startswith('"'):
                _values.append(_field_value[1:])
            else:
                _values.append(_field_value)

        result = dict(zip(_fields, _values))

        return {key: result.get(key, "") for key in result.keys() if result.get(key) != "-"}

    @classmethod
    def parse_string_as_headers(cls, value: str) -> list[str] | None:
        """
        Try to parse input string if it contains at list one of headers from specified in docs list.

        If at least one of the headers are present we use this string as string with all headers for current logs.
        Also string should start with `#` according to this specification https://www.w3.org/TR/WD-logfile.html.

        Args:
            value: str

        Returns:
            list[str] | None
        """
        if value.startswith("#") and "Fields:" in value:
            return [
                element for element in value.rstrip("\n").split(" ") if "Fields:" not in element and "#" not in element
            ]

        return None

    @classmethod
    def full_list_of_elff_fields(cls) -> list[str]:
        """
        According to docs this method specified complete list of fields available in elff log file.

        Doc:
        https://techdocs.broadcom.com/us/en/symantec-security-software/web-and-network-security/cloud-swg/help/wss-reference/accesslogformats-ref.html

        Returns:
            list[str]:
        """
        return [
            "application-name",
            "c-ip-subnet",
            "cs(Referer)",
            "cs(User-Agent)",
            "cs(X-Requested-With)",
            "cs-auth-group",
            "cs-auth-groups",
            "cs-bytes",
            "cs-categories",
            "cs-host",
            "cs-icap-error-details",
            "cs-icap-service",
            "cs-icap-status",
            "c-ip",
            "cs-method",
            "cs-threat-risk",
            "cs-uri-extension",
            "cs-uri-path",
            "cs-uri-port",
            "cs-uri-query",
            "cs-uri-scheme",
            "cs-userdn",
            "cs-version",
            "cs(X-Forwarded-For)",
            "date",
            "ear-cas-file-reputation-score",
            "ear-cs-referer",
            "ear-upload-source",
            "isolation-url",
            "ma-detonated",
            "page-views",
            "r-ip",
            "r-supplier-country",
            "risk-groups",
            "rs(Content-Type)",
            "rs-icap-error-details",
            "rs-icap-service",
            "rs-icap-status",
            "rs-version",
            "s-action",
            "s-ip",
            "s-source-ip",
            "s-supplier-country",
            "s-supplier-failures",
            "s-supplier-ip",
            "sc-bytes",
            "sc-filter-result",
            "sc-status",
            "search-terms",
            "time",
            "time-taken",
            "upload-source",
            "verdict",
            "x-bluecoat-access-type",
            "x-bluecoat-appliance-name",
            "x-bluecoat-application-name",
            "x-bluecoat-application-operation",
            "x-bluecoat-location-id",
            "x-bluecoat-location-name",
            "x-bluecoat-reference-id",
            "x-bluecoat-request-tenant-id",
            "x-bluecoat-placeholder",
            "x-bluecoat-transaction-uuid",
            "x-client-agent-sw",
            "x-client-agent-type",
            "x-client-device-id",
            "x-client-device-name",
            "x-client-device-type",
            "x-client-os",
            "x-cloud-rs",
            "x-client-security-posture-details",
            "x-client-security-posture-risk-score",
            "s-computername",
            "x-cs(referer)-uri-categories",
            "x-cs-certificate-subject",
            "x-cs-client-ip-country",
            "x-cs-connection-negotiated-cipher",
            "x-cs-connection-negotiated-cipher-size",
            "x-cs-connection-negotiated-ssl-version",
            "x-cs-ocsp-error",
            "x-data-leak-detected",
            "x-dns-cs-address",
            "x-dns-cs-category",
            "x-dns-cs-dns",
            "x-dns-cs-opcode",
            "x-dns-cs-qclass",
            "x-dns-cs-qtype",
            "x-dns-cs-threat-risk-level",
            "x-dns-cs-transport",
            "x-dns-lookup-time",
            "x-dns-rs-a-records",
            "x-dns-rs-cname-records",
            "x-dns-rs-ptr-records",
            "x-dns-rs-rcode",
            "x-exception-id",
            "x-http-connect-host",
            "x-http-connect-port",
            "x-icap-reqmod-header(X-ICAP-Metadata)",
            "x-icap-respmod-header(X-ICAP-Metadata)",
            "x-random-ipv6",
            "x-request-origin",
            "x-rs-certificate-hostname",
            "x-rs-certificate-hostname-categories",
            "x-rs-certificate-hostname-category",
            "x-rs-certificate-hostname-threat-risk",
            "x-rs-certificate-observed-errors",
            "x-rs-certificate-validate-status",
            "x-rs-connection-negotiated-cipher",
            "x-rs-connection-negotiated-cipher-size",
            "x-rs-connection-negotiated-cipher-strength",
            "x-rs-connection-negotiated-ssl-version",
            "x-rs-ocsp-error",
            "x-sc-connection-issuer-keyring",
            "x-sc-connection-issuer-keyring-alias",
            "x-sr-vpop-country",
            "x-sr-vpop-country-code",
            "x-sr-vpop-ip",
            "x-symc-dei-app",
            "x-symc-dei-via",
            "x-timestamp-unix",
            "x-virus-id",
        ]

    @classmethod
    def reduce_list(cls, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Reduce input list based on business requirements.

        Args:
            data: list[dict[str, Any]]

        Returns:
            list[dict[str, Any]]:
        """

        def _group_key(item: dict[str, Any]) -> tuple[Any, Any, Any, Any, Any, Any, Any, Any]:
            return (
                item.get("c-ip", ""),
                item.get("cs-userdn", ""),
                item.get("s-action", ""),
                item.get("s-ip", ""),
                item.get("sc-status", ""),
                item.get("cs-method", ""),
                item.get("cs-host", ""),
                item.get("cs-uri-path", ""),
            )

        # Sorting the data is important for the groupby to work correctly
        sorted_data = sorted(data, key=_group_key)

        grouped_data = {key: list(group) for key, group in groupby(sorted_data, key=_group_key)}

        result = []
        for key, group in grouped_data.items():
            if len(group) > 0:
                time_taken = int(group[0].get("time-taken", 0))
                start_time = datetime.strptime(group[0].get("time", ""), cls._time_format)
                end_time = datetime.strptime(group[0].get("time", ""), cls._time_format)
                count = 0

                for entry in group:
                    entry_time_taken = int(entry.get("time-taken", 0))
                    if time_taken < entry_time_taken:
                        time_taken = entry_time_taken

                    entry_start_time = datetime.strptime(
                        entry.get("start-time") or entry.get("time", ""), cls._time_format
                    )

                    entry_end_time = datetime.strptime(
                        entry.get("end-time") or entry.get("time", ""), cls._time_format
                    )

                    if start_time > entry_start_time:
                        start_time = entry_start_time

                    if end_time < entry_end_time:
                        end_time = entry_end_time

                    if entry.get("count", 0) != 0:
                        count += entry.get("count", 0)
                    else:
                        count += 1

                result.append(
                    {
                        **group[0],
                        "count": count,
                        "time-taken": time_taken,
                        "start-time": start_time.strftime(cls._time_format),
                        "end-time": end_time.strftime(cls._time_format),
                    }
                )

        return result

    @classmethod
    def get_date_time_from_data(cls, data: dict[str, Any]) -> datetime | None:
        """
        Try to get datetime input data.

        Args:
            data: dict[str, Any]

        Returns:
            datetime | None
        """
        if data.get("date") and data.get("time"):
            return datetime.strptime(
                "{0} {1}".format(data.get("date"), data.get("time")),
                "{0} {1}".format(cls._date_format, cls._time_format),
            )

        return None
