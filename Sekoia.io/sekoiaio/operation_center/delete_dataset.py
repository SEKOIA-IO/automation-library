from uuid import UUID
from posixpath import join as urljoin

from urllib3.exceptions import TimeoutError as Urllib3TimeoutError

from pydantic.v1 import BaseModel

from requests import Session

from requests.exceptions import HTTPError, Timeout
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)


from .base_sol import BaseSolAction


class DeleteDatasetArguments(BaseModel):
    """Input arguments for the DeleteDataset action."""

    name: str | None = None
    uuid: UUID | None = None


class DeleteDatasetResults(BaseModel):
    """Output returned by the DeleteDataset action (empty on success)."""


class DeleteDataset(BaseSolAction):
    """Action that deletes a dataset from the Sekoia notebooks API by name."""

    http_session: Session
    results_model = DeleteDatasetResults
    dataset_api_path: str

    def configure_urls(self) -> None:
        """Set up the dataset API base path."""
        self.dataset_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/datasets")

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def get_dataset_uuid(self, dataset_name: str | None) -> UUID:
        """Resolve a dataset UUID from its name within a community.

        :param dataset_name: Name of the dataset to look up
        :return: UUID of the matching dataset
        :raises ValueError: If no dataset or more than one dataset matches the given name
        """
        result: UUID

        response_list_dataset = self.http_session.get(
            url=self.dataset_api_path,
            params={
                "name": dataset_name,
            },
            timeout=60,
        )
        try:
            response_list_dataset.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when retrieving existing datasets: {e}. Response status: {response_list_dataset.status_code}, Response text: {response_list_dataset.text}",
                level="error",
            )
            raise
        response_content = response_list_dataset.json()

        if not response_content["items"]:
            self.log(
                f"No dataset found with name '{dataset_name}'",
                level="error",
            )
            raise ValueError
        elif len(response_content["items"]) > 1:
            self.log(
                f"Multiple datasets found with name '{dataset_name}'",
                level="error",
            )
            raise ValueError
        else:
            result = UUID(response_content["items"][0]["uuid"])

        return result

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def delete_dataset(self, dataset_uuid: UUID) -> None:
        """Delete a dataset by its UUID via the notebooks API.

        :param dataset_uuid: UUID of the dataset to delete
        :raises requests.exceptions.HTTPError: If the API returns an error response
        """
        response_delete = self.http_session.delete(f"{self.dataset_api_path}/{str(dataset_uuid)}", timeout=60)
        try:
            response_delete.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when deleting dataset: {e}. Response status: {response_delete.status_code}, Response text: {response_delete.text}",
                level="error",
            )
            raise

    def run(self, arguments: DeleteDatasetArguments) -> DeleteDatasetResults:
        """Resolve and delete a dataset by name from the Sekoia notebooks API.

        :param arguments: Action input arguments (dataset name)
        """
        self.configure_http_session()
        self.configure_urls()
        # Resolve the dataset UUID from its name before deleting
        if arguments.uuid is not None:
            dataset_uuid = arguments.uuid
        else:
            dataset_uuid = self.get_dataset_uuid(arguments.name)
        self.delete_dataset(dataset_uuid)
        # return empty DeleteDatasetResults on success
        return DeleteDatasetResults()
