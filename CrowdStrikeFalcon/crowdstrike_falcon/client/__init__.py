from collections.abc import Generator
from posixpath import join as urljoin
from typing import Any

import requests
from requests.auth import AuthBase
from requests.exceptions import HTTPError
from requests_ratelimiter import LimiterAdapter

from crowdstrike_falcon.client.auth import CrowdStrikeFalconApiAuthentication
from crowdstrike_falcon.client.retry import Retry
from crowdstrike_falcon.client.schemas import HostAction, UpdateAlertParameter


class ApiClient(requests.Session):
    def __init__(
        self,
        base_url: str,
        auth: AuthBase,
        nb_retries: int = 5,
        ratelimit_per_second: int = 100,
        default_headers: dict[str, str] | None = None,
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

        if default_headers:
            self.headers.update(default_headers)

    def get_url(self, endpoint: str) -> str:
        return urljoin(self._base_url, endpoint.lstrip("/"))

    @staticmethod
    def format_api_errors(content: Any) -> str | None:
        """
        Return, as a single message, the errors reported in the content of a response
        """
        if not isinstance(content, dict):
            return None

        errors = [error for error in content.get("errors") or [] if isinstance(error, dict)]
        if not errors:
            return None

        return "\n".join([f"{error.get('code')}: {error.get('message')}" for error in errors])

    def raise_for_status(self, response: requests.Response) -> None:
        """
        Raise an exception according to the status code, enriched with the errors
        reported in the body of the response, when the API provides them
        """
        try:
            response.raise_for_status()
        except HTTPError as error:
            try:
                api_errors = self.format_api_errors(response.json())
            except ValueError:
                api_errors = None

            if api_errors is None:
                raise

            msg = f"{error}. The API returns the following errors: \n{api_errors}"
            raise HTTPError(msg, response=response) from error  # type: ignore[call-arg]

    def request_endpoint(
        self, method: str, endpoint: str, cursor_pagination: bool = False, **kwargs
    ) -> Generator[Any, None, None]:
        """
        Send the request and handle the response

        Args:
            cursor_pagination: the endpoint returns an opaque continuation token in
                `meta.pagination.offset` instead of a numeric offset
                (e.g. /devices/queries/devices-scroll/v1). Numeric offsets are capped
                at 10 000 results by the API, tokens are not.
        """
        params = kwargs.pop("params", {})

        url = self.get_url(endpoint)

        still_fetching_items = True
        pagination: dict | None = None

        while still_fetching_items:
            new_params = dict(params)

            if pagination:
                # If after parameter is defined in the response, use it for the pagination
                if "after" in pagination:
                    new_params["after"] = pagination["after"]
                # Otherwise, fallback on the offset parameter if defined
                elif "offset" in pagination:
                    new_params["offset"] = pagination["offset"]

            requested_cursor = new_params.get("offset") if cursor_pagination else None

            response = self.request(method=method, url=url, params=new_params, **kwargs)

            # raise exception according the status code
            self.raise_for_status(response)

            content = response.json()

            # check for errors
            errors = self.format_api_errors(content)
            if errors:
                msg = f"The API returns the following errors: \n{errors}"
                raise HTTPError(msg, response=response)  # type: ignore[call-arg]

            pagination = content.get("meta", {}).get("pagination")

            if pagination and pagination.get("after"):
                still_fetching_items = True
            elif cursor_pagination:
                # Follow the continuation token until the API stops handing back a new one
                cursor = (pagination or {}).get("offset")
                if requested_cursor is not None and cursor == requested_cursor:
                    # The API handed back the token it was given: the scroll is not
                    # advancing, so this page only repeats the previous one. Drop it.
                    return
                still_fetching_items = bool(cursor)
            elif pagination:
                offset = pagination.get("offset")
                limit = pagination.get("limit")
                total = pagination.get("total")
                still_fetching_items = (
                    isinstance(offset, int) and isinstance(limit, int) and isinstance(total, int) and offset < total
                )
            else:
                still_fetching_items = False

            yield from content.get("resources") or []

    def request_graphql_endpoint(
        self,
        endpoint: str,
        query: str,
        data_path: list[str],
        page_info_path: list[str] | None = None,
        cursor_param: str = "after",
        **kwargs,
    ) -> Generator[Any, None, None]:
        """
        Send GraphQL request and handle cursor-based pagination.

        Args:
            endpoint: GraphQL endpoint URL
            query: GraphQL query string (must contain {cursor} placeholder for pagination)
            data_path: Path to extract nodes (e.g., ["entities", "nodes"])
            page_info_path: Path to pageInfo (e.g., ["entities", "pageInfo"]), defaults to data_path[:-1] + ["pageInfo"]
            cursor_param: Name of the cursor parameter in the query
        """
        url = self.get_url(endpoint)

        if page_info_path is None:
            page_info_path = data_path[:-1] + ["pageInfo"]

        after_cursor: str | None = None
        has_next_page = True

        while has_next_page:
            cursor_value = f'{cursor_param}: "{after_cursor}"' if after_cursor else ""
            formatted_query = query.replace("{cursor}", cursor_value)

            payload: dict[str, Any] = {"query": formatted_query}

            response = self.request(method="POST", url=url, json=payload, **kwargs)
            response.raise_for_status()

            content = response.json()

            if "errors" in content:
                errors_str = "\n".join([e.get("message", str(e)) for e in content["errors"]])
                raise HTTPError(f"GraphQL errors: {errors_str}", response=response)

            data = content.get("data", {})

            # Extract nodes using data_path
            extracted_data = data
            for key in data_path:
                extracted_data = extracted_data.get(key, {}) if isinstance(extracted_data, dict) else {}

            yield from extracted_data if isinstance(extracted_data, list) else []

            # Extract pageInfo using page_info_path
            page_info = data
            for key in page_info_path:
                page_info = page_info.get(key, {}) if isinstance(page_info, dict) else {}

            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor") if has_next_page else None

            if not after_cursor:
                has_next_page = False


class CrowdstrikeFalconClient(ApiClient):
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        nb_retries: int = 5,
        default_headers: dict[str, str] | None = None,
    ):
        _auth = CrowdStrikeFalconApiAuthentication(base_url, client_id, client_secret, default_headers=default_headers)

        super().__init__(base_url, _auth, nb_retries=nb_retries, default_headers=default_headers)

    def list_streams(self, app_id: str, **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint("GET", "/sensors/entities/datafeed/v2", params={"appId": app_id}, **kwargs)

    def get_detection_details(self, detection_ids: list[str], **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "POST",
            "/detects/entities/summaries/GET/v1",
            json={"ids": detection_ids},
            **kwargs,
        )

    def get_alert_details(self, composite_ids: list[str], **kwargs) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "POST",
            "/alerts/entities/alerts/v2",
            json={"composite_ids": composite_ids},
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

    def host_action(self, ids: list[str], action: HostAction) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "POST",
            "/devices/entities/devices-actions/v2",
            params={"action_name": action.value},
            json={"ids": ids},
        )

    def update_alerts(
        self, ids: list[str], action_parameters: list[UpdateAlertParameter]
    ) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "PATCH",
            "/alerts/entities/alerts/v3",
            json={
                "composite_ids": ids,
                "action_parameters": [action_param.dict() for action_param in action_parameters],
            },
        )

    def get_edge_types(self, **kwargs) -> Generator[str, None, None]:
        yield from self.request_endpoint("GET", "/threatgraph/queries/edge-types/v1", **kwargs)

    def list_edges(
        self, verticle_id: str, edge_type: str, scope: str = "device", **kwargs
    ) -> Generator[dict, None, None]:
        yield from self.request_endpoint(
            "GET",
            "/threatgraph/combined/edges/v1",
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
            f"/threatgraph/entities/{verticle_type}/v1",
            params={"ids": verticle_ids, "scope": scope},
            **kwargs,
        )

    def list_devices_uuids(self, limit: int, sort: str, **kwargs) -> Generator[str, None, None]:
        # devices-scroll (token pagination) instead of devices/v1: the latter refuses
        # limit + offset above 10 000, which silently caps large tenants.
        yield from self.request_endpoint(
            "GET",
            "/devices/queries/devices-scroll/v1",
            params={"limit": limit, "sort": sort},
            cursor_pagination=True,
            **kwargs,
        )

    def get_devices_infos(self, ids: list[str], **kwargs) -> Generator[dict[str, Any], None, None]:
        yield from self.request_endpoint(
            "POST",
            "/devices/entities/devices/v2",
            json={"ids": ids},
            **kwargs,
        )

    def get_host_groups(self, ids: list[str], **kwargs) -> Generator[dict[str, Any], None, None]:
        """Fetch host group details by IDs."""
        yield from self.request_endpoint(
            "GET",
            "/devices/entities/host-groups/v1",
            params={"ids": ids},
            **kwargs,
        )

    def list_identity_entities(self, query: str, **kwargs) -> Generator[dict[str, Any], None, None]:
        """Fetch identity entities from GraphQL endpoint with pagination."""
        yield from self.request_graphql_endpoint(
            endpoint="/identity-protection/combined/graphql/v1",
            query=query,
            data_path=["entities", "nodes"],
            **kwargs,
        )
