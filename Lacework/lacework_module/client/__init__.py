import requests
from requests.adapters import Retry
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter
from typing import Any

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
    auth: LaceworkAuthentication

    def __init__(
        self, base_url: str, auth: LaceworkAuthentication, nb_retries: int = 5, ratelimit_per_hour: int = 480
    ):
        super().__init__(base_url=base_url, auth=auth, nb_retries=nb_retries, ratelimit_per_hour=ratelimit_per_hour)

    def list_alerts(self, parameters: dict[Any, Any] | None = None) -> requests.Response:
        return self.get(
            url=(f"https://{self.base_url}.lacework.net/api/v2/Alerts"),
            params=parameters,
        )

    def get_alerts_from_date(self, startTime: str) -> requests.Response:
        return self.get(
            url=(f"https://{self.base_url}.lacework.net/api/v2/Alerts?startTime={startTime}"),
        )

    def get_alerts_details(self, alertId: str, scope: str) -> requests.Response:
        return self.get(
            url=(f"https://{self.base_url}.lacework.net/api/v2/Alerts/{alertId}?scope={scope}"),
        )
