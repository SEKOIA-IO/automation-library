"""Configs and wrapper to work with Azure Blob Storage."""

from typing import Tuple

import aiofiles
from azure.core.async_paging import AsyncItemPaged
from azure.storage.blob import BlobProperties
from azure.storage.blob.aio import ContainerClient
from pydantic import BaseModel


class AzureBlobStorageConfig(BaseModel):
    """Azure Blob Storage config."""

    container_name: str
    account_name: str
    account_key: str

    def get_connection_string(self) -> str:
        """
        Return connection string or generate based on inputs.

        Returns:
            str:
        """
        return "DefaultEndpointsProtocol=https;AccountName={0};AccountKey={1};EndpointSuffix=core.windows.net".format(
            self.account_name,
            self.account_key,
        )


class AzureBlobStorageWrapper(object):
    """Azure blob storage wrapper."""

    _client: ContainerClient | None = None

    def __init__(self, config: AzureBlobStorageConfig) -> None:
        """
        Initialize AzureBlobStorageWrapper.

        Args:
            config: AzureBlobStorageConfig
        """
        self._config = config

    def client(self) -> ContainerClient:  # pragma: no cover
        """
        Initialize Azure Blob Storage client.

        Returns:
            ContainerClient:
        """
        if not self._client:
            self._client = ContainerClient.from_connection_string(
                self._config.get_connection_string(),
                self._config.container_name,
            )

        return self._client

    def list_blobs(self) -> AsyncItemPaged[BlobProperties]:
        """
        List all blobs in container.

        Returns:
            AsyncItemPaged[BlobProperties]:
        """
        return self.client().list_blobs()

    async def download_blob(
        self, blob_name: str, download: bool = True, tmp_dir: str = "/tmp"
    ) -> Tuple[str | None, bytes | None]:
        """
        Download blob content from Azure Blob Storage.

        Args:
            blob_name: str
            download: bool
            tmp_dir: str

        Returns:
            Union[str, bytes]:
        """
        blob = self.client().get_blob_client(blob_name)
        stream = await blob.download_blob()

        if download:
            async with aiofiles.tempfile.NamedTemporaryFile("wb", delete=False, dir=tmp_dir) as file:
                file_name = str(file.name)
                async for chunk in stream.chunks():
                    await file.write(chunk)

                return file_name, None

        # This operation is blocking
        result = await stream.readall()

        return None, result
