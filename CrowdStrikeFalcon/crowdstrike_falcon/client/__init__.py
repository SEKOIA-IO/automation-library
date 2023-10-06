from collections.abc import Generator
from typing import Any
from urllib.parse import urljoin

import requests
from requests.auth import AuthBase, HTTPBasicAuth
from requests.exceptions import HTTPError
from requests_ratelimiter import LimiterAdapter

from crowdstrike_falcon.client.auth import CrowdStrikeFalconApiAuthentication
from crowdstrike_falcon.client.retry import Retry


class ApiClient(requests.Session):
    def __init__(
        self,
        base_url: str,
        auth: AuthBase,
        nb_retries: int = 5,
        ratelimit_per_second: int = 100,
    ):
        super().__init__()
        self._base_url = base_url
        self.auth = auth
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

    def get_url(self, endpoint: str) -> str:
        return urljoin(self._base_url, endpoint)

    def request_endpoint(self, method: str, endpoint: str, **kwargs) -> Generator[Any, None, None]:
        """
        Send the request and handle the response
        """
        params = kwargs.pop("params", {})

        url = self.get_url(endpoint)

        still_fetching_items = True
        pagination: dict | None = None

        while still_fetching_items:
            new_params = dict(params)

            if pagination and "offset" in pagination:
                new_params["offset"] = pagination["offset"]

            response = self.request(method=method, url=url, params=new_params, **kwargs)

            # raise exception according the status code
            response.raise_for_status()

            content = response.json()

            # check for errors
            errors = content.get("errors", [])
            if errors and len(errors):
                errors_str = "\n".join([f"{error['code']}: {error['message']}" for error in errors])
                msg = f"The API returns the following errors: \n{errors_str}"
                raise HTTPError(msg, response=response)  # type: ignore[call-arg]
            yield from content.get("resources") or []

            pagination = content.get("meta", {}).get("pagination")
            still_fetching_items = pagination is not None


class CrowdstrikeFalconClient(ApiClient):
    def __init__(self, base_url: str, client_id: str, client_secret: str, nb_retries: int = 5):
        super().__init__(
            base_url,
            CrowdStrikeFalconApiAuthentication(base_url, client_id, client_secret),
            nb_retries=nb_retries,
        )

    def list_streams(self, app_id: str, **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint("GET", "/sensors/entities/datafeed/v2", params={"appId": app_id}, **kwargs)

    def get_detection_details(self, detection_ids: list[str], **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "POST",
            "/detects/entities/summaries/GET/v1",
            json={"ids": detection_ids},
            **kwargs,
        )

    def find_indicators(self, fql_filter, **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "GET",
            "/iocs/queries/indicators/v1",
            params={"filter": fql_filter},
            **kwargs,
        )

    def upload_indicators(self, indicators: list, **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "POST",
            "/iocs/entities/indicators/v1",
            json={"indicators": indicators},
            params={"ignore_warnings": "true"},
            **kwargs,
        )

    def delete_indicators(self, ids: list, **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "DELETE",
            "/iocs/entities/indicators/v1",
            params={"ids": ids},
            **kwargs,
        )


class CrowdstrikeThreatGraphClient(ApiClient):
    def __init__(self, base_url: str, username: str, password: str, nb_retries: int = 5):
        super().__init__(base_url, HTTPBasicAuth(username, password), nb_retries=nb_retries)

    def get_edge_types(self, **kwargs) -> Generator[str, None, None]:
        yield from self.request_endpoint("GET", "threatgraph/queries/edge-types/v1", **kwargs)

    def list_edges(
        self, verticle_id: str, edge_type: str, scope: str = "device", **kwargs
    ) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "GET",
            "threatgraph/combined/edges/v1",
            params={"ids": verticle_id, "edge_type": edge_type, "scope": scope},
            **kwargs,
        )

    def get_verticles_details(
        self,
        verticle_ids: list[str],
        verticle_type: str,
        scope: str = "device",
        **kwargs,
    ) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "GET",
            f"threatgraph/entities/{verticle_type}/v1",
            params={"ids": verticle_ids, "scope": scope},
            **kwargs,
        )
