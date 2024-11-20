from typing import Any

import requests
from requests.adapters import Retry
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from sophos_module.client.auth import SophosApiAuthentication


class ApiClient(requests.Session):
    def __init__(
        self,
        auth: AuthBase,
        nb_retries: int = 5,
        ratelimit_per_second: int = 10,
        ratelimit_per_minute: int = 100,
        ratelimit_per_hour: int = 1000,
        ratelimit_per_day: int = 200000,
    ):
        super().__init__()
        self.auth = auth
        adapter = LimiterAdapter(
            per_second=ratelimit_per_second,
            per_minute=ratelimit_per_minute,
            per_hour=ratelimit_per_hour,
            per_day=ratelimit_per_day,
            max_retries=Retry(total=nb_retries, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]),
        )
        self.mount("http://", adapter)
        self.mount("https://", adapter)


class SophosApiClient(ApiClient):
    auth: SophosApiAuthentication

    def __init__(
        self,
        auth: SophosApiAuthentication,
        nb_retries: int = 5,
        ratelimit_per_second: int = 10,
        ratelimit_per_minute: int = 100,
        ratelimit_per_hour: int = 1000,
        ratelimit_per_day: int = 200000,
    ) -> None:
        super().__init__(
            auth=auth,
            nb_retries=nb_retries,
            ratelimit_per_second=ratelimit_per_second,
            ratelimit_per_minute=ratelimit_per_minute,
            ratelimit_per_hour=ratelimit_per_hour,
            ratelimit_per_day=ratelimit_per_day,
        )

    def list_siem_events(self, parameters: dict[str, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/siem/v1/events",
            params=parameters,
        )

    def run_query(self, json_query: dict[str, Any]) -> requests.Response:
        return self.post(url=f"{self.auth.get_credentials().api_url}/xdr-query/v1/queries/runs", json=json_query)

    def get_query_status(self, run_id: str) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/xdr-query/v1/queries/runs/{run_id}",
        )

    def get_query_results(self, run_id: str | None, page_size: int, from_key: str | None = None) -> requests.Response:
        if run_id is None:
            raise ValueError("run_id is required")

        params: dict[str, Any] = {"maxSize": 1000, "pageSize": page_size}
        if from_key:
            params["pageFromKey"] = from_key

        return self.get(
            url=f"{self.auth.get_credentials().api_url}/xdr-query/v1/queries/runs/{run_id}/results",
            params=params,
        )
