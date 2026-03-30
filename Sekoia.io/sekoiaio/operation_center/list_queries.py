from uuid import UUID
from requests import Session
from posixpath import join as urljoin
from urllib3.util.retry import Retry
from typing import Any

from pydantic.v1 import BaseModel
from sekoia_automation.action import Action
import urllib3

import requests
import urllib3
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from sekoia_automation.action import Action
from sekoiaio.utils import user_agent


class ListQueriesArguments(BaseModel):
    """Input arguments for the ListQueries action."""


class ListQueriesResults(BaseModel):
    """Output returned by the ListQueries action."""

    queries: list[dict[str, Any]]


class ListQueries(Action):
    """Action that retrieves all SOL queries available."""

    http_session: Session
    query_api_path: str

    results_model = ListQueriesResults

    def configure_http_session(self) -> None:
        """Set up the query API base path and configure the HTTP session with retry and auth headers."""
        self.query_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/queries")

        # Configure http with retry strategy
        retry_strategy = Retry(
            total=10,  # Total number of retries for all types of errors
            status=10,  # Number of retries specifically for responses with status codes in status_forcelist
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
            backoff_max=120,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session = requests.Session()
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)
        self.http_session.headers = CaseInsensitiveDict(
            data={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.module.configuration['api_key']}",
                "User-Agent": user_agent(),
            }
        )

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def get_queries(self) -> list[dict[str, Any]]:
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
                },
                timeout=20,
            )
            try:
                response_list_query.raise_for_status()
            except requests.exceptions.HTTPError as e:
                self.log(
                    f"HTTP error when retrieving existing queries: {e}. Response status: {response_list_query.status_code}, Response text: {response_list_query.text}",
                    level="error",
                )
                raise
            response_content = response_list_query.json()

            if not response_content["items"]:
                num_results = len(results)
                if num_results < response_content["total"] and num_results < limit:
                    self.log(
                        "Number of fetched results doesn't match total",
                        level="error",
                        num_results=num_results,
                        total=response_content["total"],
                    )
                break
            results += response_content["items"]
            total = min(response_content["total"], limit)

            offset += limit
        return results

    def run(self, arguments: ListQueriesArguments) -> ListQueriesResults:
        """List all SOL queries available.

        :param arguments: Action input arguments
        :return: Action result containing the list of queries
        """
        self.configure_http_session()
        # Retrieve all queries.
        queries = self.get_queries()
        return ListQueriesResults(queries=queries)
