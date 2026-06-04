from requests import Session
from posixpath import join as urljoin

from typing import Any

from pydantic.v1 import BaseModel

from urllib3.exceptions import TimeoutError as Urllib3TimeoutError

from requests.exceptions import Timeout, HTTPError

from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from .base_sol import BaseSolAction


def bool_to_param(value):
    if value is None:
        return None  # requests will omit the key
    return str(value).lower()  # True → "true", False → "false"


class ListQueriesArguments(BaseModel):
    """Input arguments for the ListQueries action."""

    match_uuid: str | None = None
    match_name: str | None = None
    match_visualization: str | None = None
    match_isshared: bool | None = None
    match_created_by: str | None = None
    parameters: str | None = None


class ListQueriesResults(BaseModel):
    """Output returned by the ListQueries action."""

    queries: list[dict[str, Any]]


class ListQueries(BaseSolAction):
    """Action that retrieves all SOL queries available."""

    http_session: Session
    query_api_path: str

    results_model = ListQueriesResults

    def configure_urls(self) -> None:
        """Set up the query API base path."""
        self.query_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/queries")

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_queries(self, argument: ListQueriesArguments) -> list[dict[str, Any]]:
        """Retrieve all SOL queries, with pagination.

        :return: List of query definition dicts
        """
        results: list[dict[str, Any]] = []
        limit = 100
        total = None
        offset = 0

        while total is None or total > offset:
            response_list_query = self.http_session.get(
                url=self.query_api_path,
                params={
                    "limit": limit,
                    "offset": offset,
                    "match[uuid]": argument.match_uuid,
                    "match[name]": argument.match_name,
                    "match[visualization]": argument.match_visualization,
                    "match[is_shared]": bool_to_param(argument.match_isshared),
                    "match[created_by]": argument.match_created_by,
                    "parameters": argument.parameters,
                },
                timeout=60,
            )
            try:
                response_list_query.raise_for_status()
            except HTTPError as e:
                self.log(
                    f"HTTP error when retrieving existing queries: {e}. Response status: {response_list_query.status_code}, Response text: {response_list_query.text}",
                    level="error",
                )
                raise
            response_content = response_list_query.json()

            if not response_content["items"]:
                num_results = len(results)
                if num_results < response_content["total"]:
                    self.log(
                        "Number of fetched results doesn't match total",
                        level="error",
                        num_results=num_results,
                        total=response_content["total"],
                    )
                break
            results += response_content["items"]
            total = response_content["total"]

            offset += limit
        return results

    def run(self, arguments: ListQueriesArguments) -> ListQueriesResults:
        """List all SOL queries available.

        :param arguments: Action input arguments
        :return: Action result containing the list of queries
        """
        self.configure_http_session()
        self.configure_urls()
        # Retrieve all queries.
        queries = self.get_queries(arguments)
        return ListQueriesResults(queries=queries)
