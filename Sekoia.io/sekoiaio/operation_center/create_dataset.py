from uuid import UUID
from requests import Session
from posixpath import join as urljoin
from urllib3.util.retry import Retry

from pydantic.v1 import BaseModel
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


class CreateDatasetArguments(BaseModel):
    """Input arguments for the CreateDataset action."""

    name: str
    dataset: str


class CreateDatasetResults(BaseModel):
    """Output returned by the CreateDataset action (empty on success)."""


class CreateDataset(Action):
    """Action that validates and uploads a CSV dataset to the Sekoia notebooks API."""

    http_session: Session
    dataset_api_path: str

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
    def validate_dataset(self, dataset: bytes, name: str) -> None:
        """Send the dataset to the validation endpoint before creation.

        :param dataset: Raw CSV content as bytes
        :param name: Name to assign to the dataset
        :raises requests.exceptions.HTTPError: If the API rejects the dataset
        """
        response_validate = self.http_session.post(
            f"{self.dataset_api_path}/validate",
            data={"name": name},
            files={"file": ("dataset.csv", dataset, "text/csv")},
        )
        try:
            response_validate.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self.log(
                f"HTTP error when validating dataset: {e}. Response status: {response_validate.status_code}, Response text: {response_validate.text}",
                level="error",
            )
            raise

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(requests.exceptions.Timeout)
        | retry_if_exception_type(urllib3.exceptions.TimeoutError),
    )
    def create_dataset(self, dataset: bytes, name: str) -> None:
        """Upload and create the dataset via the notebooks API.

        :param dataset: Raw CSV content as bytes
        :param name: Name to assign to the dataset
        :raises requests.exceptions.HTTPError: If the API returns an error response
        """
        response_create = self.http_session.post(
            self.dataset_api_path,
            data={"name": name},
            files={"file": ("dataset.csv", dataset, "text/csv")},
        )
        try:
            response_create.raise_for_status()
        except requests.exceptions.HTTPError as e:
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
            self.log(f"Error encoding dataset: {e}")
            raise

    def run(self, arguments: CreateDatasetArguments) -> CreateDatasetResults:
        """Validate and create a dataset in the Sekoia notebooks API.

        :param arguments: Action input arguments (dataset content, name)
        :return: Empty result on success
        """
        self.configure_http_session()

        # Encode the dataset string to bytes for multipart upload
        encoded_dataset = self.encode_dataset(arguments.dataset)
        # Validate the dataset before uploading
        self.validate_dataset(encoded_dataset, arguments.name)
        # Create the dataset
        self.create_dataset(encoded_dataset, arguments.name)
