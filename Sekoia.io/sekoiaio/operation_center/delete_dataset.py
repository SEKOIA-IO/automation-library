from uuid import UUID
from requests import Session
from posixpath import join as urljoin
from urllib3.util.retry import Retry

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


class DeleteDatasetArguments(BaseModel):
    """Input arguments for the DeleteDataset action."""

    name: str


class DeleteDatasetResults(BaseModel):
    """Output returned by the DeleteDataset action (empty on success)."""


class DeleteDataset(Action):
    """Action that deletes a dataset from the Sekoia notebooks API by name."""

    http_session: Session
    dataset_api_path: str

    results_model = DeleteDatasetResults

    def configure_http_session(self) -> None:
        """Set up the dataset API base path and configure the HTTP session with retry and auth headers."""
        self.dataset_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/datasets")

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
    def get_dataset_uuid(self, dataset_name: str) -> UUID:
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
            timeout=20,
        )
        try:
            response_list_dataset.raise_for_status()
        except requests.exceptions.HTTPError as e:
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
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def delete_dataset(self, dataset_uuid: str) -> None:
        """Delete a dataset by its UUID via the notebooks API.

        :param dataset_uuid: UUID of the dataset to delete
        :raises requests.exceptions.HTTPError: If the API returns an error response
        """
        response_delete = self.http_session.delete(f"{self.dataset_api_path}/{dataset_uuid}")
        try:
            response_delete.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.log(
                f"HTTP error when deleting dataset: {e}. Response status: {response_delete.status_code}, Response text: {response_delete.text}",
                level="error",
            )
            raise

    def run(self, arguments: DeleteDatasetArguments) -> DeleteDatasetResults:
        """Resolve and delete a dataset by name from the Sekoia notebooks API.

        :param arguments: Action input arguments (dataset name and community UUID)
        """
        self.configure_http_session()
        # Resolve the dataset UUID from its name before deleting
        dataset_uuid = self.get_dataset_uuid(arguments.name)
        self.delete_dataset(dataset_uuid)
        # return empty DeleteDatasetResults on success
        return DeleteDatasetResults()
