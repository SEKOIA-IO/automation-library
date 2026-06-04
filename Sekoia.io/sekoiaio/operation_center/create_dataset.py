from posixpath import join as urljoin

from pydantic.v1 import BaseModel

from requests import Session
from requests.exceptions import Timeout, HTTPError


from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from urllib3.exceptions import TimeoutError as Urllib3TimeoutError

from .base_sol import BaseSolAction


class CreateDatasetArguments(BaseModel):
    """Input arguments for the CreateDataset action."""

    name: str
    dataset: str


class CreateDatasetResults(BaseModel):
    """Output returned by the CreateDataset action (empty on success)."""


class CreateDataset(BaseSolAction):
    """Action that validates and uploads a CSV dataset to the Sekoia notebooks API."""

    http_session: Session
    dataset_api_path: str

    results_model = CreateDatasetResults

    def configure_urls(self) -> None:
        """Set up the dataset API base path."""
        self.dataset_api_path = urljoin(self.module.configuration["base_url"], "api/v1/notebooks/datasets")

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(Timeout) | retry_if_exception_type(Urllib3TimeoutError),
    )
    def create_dataset(self, dataset: bytes, name: str) -> None:
        """Upload and create the dataset via the notebooks API.

        :param dataset: Raw CSV content as bytes
        :param name: Name to assign to the dataset
        :raises requests.exceptions.HTTPError: If the API returns an error response
        """
        response_create = self.http_session.post(
            self.dataset_api_path,
            data={"name": name, "community_uuid": self.community_uuid},
            files={"file": ("dataset.csv", dataset, "text/csv")},
            timeout=60,
        )
        try:
            response_create.raise_for_status()
        except HTTPError as e:
            self.log(
                f"HTTP error when creating dataset: {e}. Response status: {response_create.status_code}, Response text: {response_create.text}",
                level="error",
            )
            raise

    def encode_dataset(self, dataset: str) -> bytes:
        """Encode the dataset string to UTF-8 bytes for multipart upload.

        :param dataset: Raw dataset content as a string
        :return: UTF-8 encoded bytes
        :raises UnicodeEncodeError: If the string cannot be encoded
        """
        try:
            return dataset.encode("utf-8")
        except UnicodeEncodeError as e:
            self.log(
                f"Error encoding dataset: {e}",
                level="error",
            )
            raise

    def run(self, arguments: CreateDatasetArguments) -> CreateDatasetResults:
        """Validate and create a dataset in the Sekoia notebooks API.

        :param arguments: Action input arguments (dataset content, name)
        :return: Empty result on success
        """
        self.configure_http_session()
        self.configure_urls()

        # Encode the dataset string to bytes for multipart upload
        encoded_dataset = self.encode_dataset(arguments.dataset)

        # Create the dataset, the validation is built-in in the API and will return an error if the dataset is not valid
        self.create_dataset(encoded_dataset, arguments.name)
        return CreateDatasetResults()
