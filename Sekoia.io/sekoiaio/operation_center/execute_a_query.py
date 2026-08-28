from uuid import UUID, uuid4

from posixpath import join as urljoin

from time import sleep, time

from typing import Any, Callable, Literal

from pydantic import BaseModel

from urllib3.exceptions import TimeoutError as Urllib3TimeoutError

from requests import Session
from requests.exceptions import Timeout, HTTPError

from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from .base_sol import BaseSolAction


class QueryExecutionError(Exception):
    """Raised when a SOL query run ends in an error or cannot be monitored."""


class QueryListingError(Exception):
    """Raised when the query listing returns an ambiguous or unexpected result."""


class ExecuteAQueryArguments(BaseModel):
    """Input arguments for the ExecuteAQuery action."""

    query_name: str | None = None
    query_uuid: UUID | None = None
    parameters: dict | None = None
    result_format: Literal["jsonl", "csv"]
    to_file: bool = False


class ExecuteAQueryResults(BaseModel):
    """Output returned by the ExecuteAQuery action."""

    query_result: str | None = None
    output_path: str | None = None


class ExecuteAQuery(BaseSolAction):
    """Action that executes a SOL (Sekoia Query Language) query and returns its result.

    Resolves the query by UUID or by name, triggers an asynchronous execution run,
    waits for it to complete, and downloads the result in the requested format.
    """

    http_session: Session
    query_api_path: str
    query_runs_api_path: str

    results_model = ExecuteAQueryResults

    def configure_urls(self) -> None:
        """Set up API base paths and configure the HTTP session with retry and auth headers."""
        self.query_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/queries")
        self.query_runs_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/queries/runs")

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def trigger_query_execution(
        self, query_uuid: UUID, query_definition: dict[str, Any], query_parameters: dict | None
    ) -> str:
        """Trigger the asynchronous execution of a SOL query and return the run UUID.

        :param query_uuid: UUID of the query to execute
        :param query_definition: SOL query definition object
        :param query_parameters: Optional dict of named parameters passed to the query
        :return: UUID of the created query run
        """
        response_execute_query = self.http_session.post(
            url=self.query_runs_api_path,
            json={
                "query_uuid": str(query_uuid),
                "query_definition": query_definition,
                "query_parameters": query_parameters,
            },
            timeout=60,
        )
        try:
            response_execute_query.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when triggering query execution for query_uuid '{query_uuid}': {e}. Response status: {response_execute_query.status_code}, Response text: {response_execute_query.text}",
                level="error",
            )
            raise
        result = response_execute_query.json()
        return result["uuid"]

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_query_by_name(self, query_name: str | None) -> dict[str, Any]:
        """Retrieve a query definition by its name, optionally scoped to a community.

        Check the first page of results and raises QueryListingError if more
        than one query matches, to avoid ambiguous execution.

        :param query_name: Name of the query to look up
        :return: Query definition dict
        :raises QueryListingError: If multiple queries match the given name and community
        """
        results: list[dict[str, Any]] = []

        response_list_query = self.http_session.get(
            url=self.query_api_path,
            params={
                "match[name]": query_name,
                "limit": 100,
                "offset": 0,
            },
            timeout=60,
        )
        try:
            response_list_query.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when retrieving existing queries matching '{query_name}': {e}. Response status: {response_list_query.status_code}, Response text: {response_list_query.text}",
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
                raise QueryListingError

        results += response_content["items"]

        if not results:
            self.log(
                f"No query found with name '{query_name}'",
                level="error",
                query_name=query_name,
            )
            raise QueryListingError

        if len(results) > 1:
            self.log(
                f"found {len(results)} queries matching name '{query_name}'. Raising an error. Consider using query_uuid to avoid this ambiguity.",
                level="error",
                num_results=len(results),
                query_name=query_name,
            )
            raise QueryListingError

        result = results[0]
        return result

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_query_by_uuid(self, query_uuid: UUID | None) -> dict[str, Any]:
        """Retrieve a query definition by its UUID.

        :param query_uuid: UUID of the query to retrieve
        :return: Query definition dict
        """
        response_get_query = self.http_session.get(
            url=urljoin(self.query_api_path, str(query_uuid)),
            timeout=60,
        )
        try:
            response_get_query.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when retrieving query definition for query_uuid '{query_uuid}': {e}. Response status: {response_get_query.status_code}, Response text: {response_get_query.text}",
                level="error",
            )
            raise
        result = response_get_query.json()
        return result

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def download_query_result(self, run_uuid: str, result_format: str) -> str | None:
        """Download the result of a completed query run.

        :param run_uuid: UUID of the query run whose result should be downloaded
        :param result_format: Desired output format, either "jsonl" or "csv"
        :return: Raw result content as a string, or None if the query returned no results
        """
        response_download_result = self.http_session.get(
            url=urljoin(self.query_runs_api_path, f"{run_uuid}/download"),
            timeout=60,
            params={"download_format": result_format},
        )
        if response_download_result.status_code == 404:
            try:
                error_code = response_download_result.json().get("detail", {}).get("code")
            except Exception:
                error_code = None
            if error_code == "NO_RESULTS":
                self.log(
                    f"Query run '{run_uuid}' returned no results.",
                    level="info",
                )
                return None
        try:
            response_download_result.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when downloading query result for run_uuid '{run_uuid}': {e}. Response status: {response_download_result.status_code}, Response text: {response_download_result.text}",
                level="error",
            )
            raise
        result = response_download_result.text
        return result

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def _wait_for_query_completion_step(
        self, run_uuid: str, should_we_wait: Callable[[str], bool], timeout: int
    ) -> None:
        """Poll a query run until the given condition is no longer met or the timeout expires.

        :param run_uuid: UUID of the query run to monitor
        :param should_we_wait: Callable that returns True as long as polling should continue
        :param timeout: Maximum number of seconds to wait before raising TimeoutError
        :raises QueryExecutionError: If the run status is "error" or the status cannot be retrieved
        :raises TimeoutError: If the run does not reach the expected state within the timeout
        """
        start_wait = time()

        response_get_run = self.http_session.get(
            url=urljoin(self.query_runs_api_path, run_uuid),
            timeout=60,
        )
        try:
            response_get_run.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when retrieving query run status for run_uuid '{run_uuid}': {e}. Response status: {response_get_run.status_code}, Response text: {response_get_run.text}",
                level="error",
            )
            raise
        status = response_get_run.json()["status"]
        if status == "error":
            error = response_get_run.json()["error"]
            self.log(
                f"Query run '{run_uuid}' ended with error: {error}",
                level="error",
                run_uuid=run_uuid,
                error=error,
            )
            raise QueryExecutionError

        while should_we_wait(status):
            sleep(1)

            response_get_run = self.http_session.get(
                url=urljoin(self.query_runs_api_path, run_uuid),
                timeout=60,
            )
            try:
                response_get_run.raise_for_status()
            except HTTPError as e:
                self.log(
                    f"HTTP error when retrieving query run status for run_uuid '{run_uuid}': {e}. Response status: {response_get_run.status_code}, Response text: {response_get_run.text}",
                    level="error",
                )
                raise
            status = response_get_run.json()["status"]
            if status == "error":
                error = response_get_run.json()["error"]
                self.log(
                    f"Query run '{run_uuid}' ended with error: {error}",
                    level="error",
                    run_uuid=run_uuid,
                    error=error,
                )
                raise QueryExecutionError

            if time() - start_wait > timeout:
                raise TimeoutError(f"Timeout while waiting for query run '{run_uuid}' to complete.")

    def wait_for_query_completion(self, run_uuid: str) -> None:
        """Wait for a query run to transition from pending to running, then to a terminal state.

        :param run_uuid: UUID of the query run to wait on
        :raises QueryExecutionError: If the run ends in error at either phase
        :raises TimeoutError: If the run does not complete within the allowed time windows
        """
        self._wait_for_query_completion_step(run_uuid, lambda status: status == "pending", timeout=1200)
        self.log(
            f"Query run '{run_uuid}' is now running. Waiting for it to complete...",
            run_uuid=run_uuid,
        )

        self._wait_for_query_completion_step(run_uuid, lambda status: status == "running", timeout=1800)
        self.log(f"Query run '{run_uuid}' has completed.", run_uuid=run_uuid)

    def save_to_file(self, result: str, file_format: str) -> str:
        filename = f"query_output-{uuid4()}.{file_format}"
        with self._data_path.joinpath(filename).open("w", encoding="utf-8") as f:
            if isinstance(result, str):
                f.write(result)
        return filename

    def run(self, arguments: ExecuteAQueryArguments) -> ExecuteAQueryResults:
        """Execute a SOL query and return its result.

        :param arguments: Action input arguments (query identifier, parameters, output format)
        :return: Action result containing the raw query output
        """
        self.configure_http_session()
        self.configure_urls()

        # Resolve the query definition by UUID if provided, otherwise fall back to name lookup
        if arguments.query_uuid:
            query = self.get_query_by_uuid(arguments.query_uuid)
        else:
            query = self.get_query_by_name(arguments.query_name)

        # Remove `community_uuids` from further request, as it contains all workspace communities.
        # Without it, we will target the current community and avoid permissions error.
        community_uuids = query.get("definition", {}).get("community_uuids")
        if community_uuids:
            del query["definition"]["community_uuids"]

        # Trigger the asynchronous query execution run
        run_uuid = self.trigger_query_execution(
            query_uuid=UUID(query["uuid"]),
            query_definition=query["definition"],
            query_parameters=arguments.parameters,
        )

        # Wait for the run to reach a terminal state
        self.wait_for_query_completion(run_uuid=run_uuid)

        # Download the result in the requested format
        result = self.download_query_result(run_uuid=run_uuid, result_format=arguments.result_format)

        self.log(
            f"Query execution completed successfully for query_uuid '{query['uuid']}' and run_uuid '{run_uuid}'.",
            query_uuid=query["uuid"],
            run_uuid=run_uuid,
        )
        if result is None:
            return ExecuteAQueryResults(query_result=None, output_path=None)
        if arguments.to_file:
            filepath = self.save_to_file(result, arguments.result_format)
            return ExecuteAQueryResults(query_result=None, output_path=filepath)
        return ExecuteAQueryResults(query_result=result, output_path=None)
