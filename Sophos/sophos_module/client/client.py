from typing import Any

import requests
from requests.adapters import Retry
from requests.auth import AuthBase
from requests_ratelimiter import LimiterAdapter

from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosGraphQLError
from sophos_module.client.helpers import retry

DEFAULT_GRAPHQL_API_URL = "https://api.taegis.sophos.com"
# seconds: default timeout of the REST requests, so a stalled connection never blocks a trigger
REQUEST_TIMEOUT = 60
# seconds: GraphQL requests of the collection, and of the optional checks (single attempt)
GRAPHQL_TIMEOUT = 60
BEST_EFFORT_GRAPHQL_TIMEOUT = 10


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

    def request(self, method: str | bytes, url: str | bytes, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return super().request(method, url, *args, **kwargs)


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
        graphql_api_url: str = DEFAULT_GRAPHQL_API_URL,
    ) -> None:
        self.graphql_api_url = graphql_api_url.rstrip("/")
        super().__init__(
            auth=auth,
            nb_retries=nb_retries,
            ratelimit_per_second=ratelimit_per_second,
            ratelimit_per_minute=ratelimit_per_minute,
            ratelimit_per_hour=ratelimit_per_hour,
            ratelimit_per_day=ratelimit_per_day,
        )

    @retry()
    def list_siem_events(self, parameters: dict[str, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/siem/v1/events",
            params=parameters,
        )

    @retry()
    def run_query(self, json_query: dict[str, Any]) -> requests.Response:
        return self.post(url=f"{self.auth.get_credentials().api_url}/xdr-query/v1/queries/runs", json=json_query)

    @retry()
    def get_query_status(self, run_id: str, timeout: float = REQUEST_TIMEOUT) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/xdr-query/v1/queries/runs/{run_id}",
            timeout=timeout,
        )

    @retry()
    def list_endpoints(self, parameters: dict[str, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/endpoint/v1/endpoints",
            params=parameters,
        )

    @retry()
    def list_directory_users(self, parameters: dict[str, Any] | None = None) -> requests.Response:
        return self.get(
            url=f"{self.auth.get_credentials().api_url}/common/v1/directory/users",
            params=parameters,
        )

    @retry()
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

    @retry()
    def _post_graphql(self, query: str, variables: dict[str, Any] | None) -> requests.Response:
        response = self.post(
            url=f"{self.graphql_api_url}/graphql",
            json={"query": query, "variables": variables or {}},
            timeout=GRAPHQL_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def _post_graphql_once(self, query: str, variables: dict[str, Any] | None) -> requests.Response:
        # plain request: none of the retries of this session (urllib3 adapter, tenacity), short timeout
        response = requests.post(
            url=f"{self.graphql_api_url}/graphql",
            json={"query": query, "variables": variables or {}},
            auth=self.auth,
            timeout=BEST_EFFORT_GRAPHQL_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def graphql(
        self, query: str, variables: dict[str, Any] | None = None, best_effort: bool = False
    ) -> dict[str, Any]:
        """
        Run a query on the Sophos Fusion GraphQL API and return its `data`.

        The API answers HTTP 200 on query errors (invalid query, downstream errors):
        a non-empty `errors` array raises SophosGraphQLError.

        best_effort: one attempt with a short timeout, for optional checks that must never delay the collection.
        """
        response = self._post_graphql_once(query, variables) if best_effort else self._post_graphql(query, variables)
        body = response.json()
        errors = body.get("errors")
        if errors:
            raise SophosGraphQLError(errors)

        data: dict[str, Any] = body.get("data") or {}
        return data
