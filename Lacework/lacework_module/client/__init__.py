from datetime import datetime, timezone
from typing import Any, Tuple

import requests
from requests.adapters import Retry
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from lacework_module.client.auth import LaceworkAuthentication


class ApiClient(requests.Session):
    def __init__(self, base_url: str, auth: AuthBase, nb_retries: int = 5, ratelimit_per_hour: int = 480):
        super().__init__()
        self.base_url = base_url
        self.auth = auth
        adapter = LimiterAdapter(
            per_hour=ratelimit_per_hour,
            max_retries=Retry(total=nb_retries, backoff_factor=1),
        )
        self.mount("http://", adapter)
        self.mount("https://", adapter)


class LaceworkApiClient(ApiClient):
    """
    Docs:
        https://docs.lacework.net/api/v2/docs#tag/Alerts/paths/~1api~1v2~1Alerts/get
        https://docs.lacework.net/api/about-the-lacework-api
    """

    auth: LaceworkAuthentication

    def get_alerts_from_date_url(self, start_time: str) -> str:
        return f"https://{self.base_url}/api/v2/Alerts?startTime={start_time}"

    def list_alerts(self, parameters: dict[Any, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"https://{self.base_url}/api/v2/Alerts",
            params=parameters,
        )

    def get_alerts_by_date(self, date: datetime) -> Tuple[list[dict[str, Any]] | None, str | None]:
        """
        Get alerts from a specific date.

        Args:
            date: datetime

        Returns:
            Tuple[list[dict[str, Any]] | None, str | None]:
        """
        request_url = self.get_alerts_from_date_url(date.strftime("%Y-%m-%dT%H:%M:%SZ"))

        response = self.get(request_url)
        if not response.ok:
            raise ValueError(f"Request failed with status {response.status_code} - {response.reason}")

        return self._parse_alerts_response(response.json())

    def get_alerts_by_page(self, url: str) -> Tuple[list[dict[str, Any]] | None, str | None]:
        """
        Get alerts by page.

        Args:
            url: str

        Returns:
            Tuple[list[dict[str, Any]] | None, str | None]:
        """
        response = self.get(url=url)
        if not response.ok:
            raise ValueError(
                f"Request to fetch next page events failed with status {response.status_code} - {response.reason}"
            )

        return self._parse_alerts_response(response.json())

    @staticmethod
    def _parse_alerts_response(result: dict[str, Any]) -> Tuple[list[dict[str, Any]] | None, str | None]:
        """
        Parse the response from the Lacework API and return the data and the next page URL.

        Args:
            response: Response

        Returns:
            Tuple[list[dict[str, Any]] | None, str | None]:
        """
        next_page_url: str | None = result.get("paging", {}).get("urls", {}).get("nextPage")

        return result.get("data"), next_page_url

    @staticmethod
    def parse_response_time(value: str) -> datetime:
        """
        Parse time field from Lacework API with correct format and lift it to UTC timezone.

        Args:
            value: str

        Returns:
            datetime:
        """
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

    @staticmethod
    def get_next_page_url(response: dict[str, Any]) -> str | None:
        """
        Get the next page URL from the Lacework API response.

        Args:
            response:  dict[str, Any]

        Returns:
            str | None:
        """
        result: str | None = response.get("paging", {}).get("urls", {}).get("nextPage")

        return result
