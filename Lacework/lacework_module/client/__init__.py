from datetime import datetime, timezone
from typing import Any

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

    def list_alerts(self, parameters: dict[Any, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"https://{self.base_url}/api/v2/Alerts",
            params=parameters,
        )

    def get_alerts_from_date(self, start_time: str) -> requests.Response:
        return self.get(
            url=f"https://{self.base_url}/api/v2/Alerts?startTime={start_time}",
        )

    @staticmethod
    def parse_event_time(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

    @staticmethod
    def get_next_page_url(response: dict[str, Any]) -> str | None:
        result: str | None = response.get("paging", {}).get("urls", {}).get("nextPage")

        return result
