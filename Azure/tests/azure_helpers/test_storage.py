"""Tests related to storage wrapper."""

import datetime
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.storage.blob import BlobProperties

from azure_helpers.storage import AzureBlobStorageConfig, AzureBlobStorageWrapper


@pytest.fixture
def config(container_name, account_name, account_key) -> AzureBlobStorageConfig:
    """
    Init AzureBlobStorageConfig.

    Args:
        container_name: str
        account_name: str
        account_key: str

    Returns:
        AzureBlobStorageConfig:
    """
    return AzureBlobStorageConfig(container_name=container_name, account_name=account_name, account_key=account_key)


@pytest.fixture
def wrapper(config) -> AzureBlobStorageWrapper:
    """
    Init AzureBlobStorageWrapper.

    Args:
        config: AzureBlobStorageConfig

    Returns:
        AzureBlobStorageWrapper:
    """
    return AzureBlobStorageWrapper(config)


@pytest.mark.asyncio
async def test_connection_string(config):
    """
    Test connection string from AzureBlobStorageConfig.

    Args:
        config: AzureBlobStorageConfig
    """
    assert config.get_connection_string() == (
        "DefaultEndpointsProtocol=https;AccountName={0};AccountKey={1};EndpointSuffix=core.windows.net".format(
            config.account_name,
            config.account_key,
        )
    )


@pytest.mark.asyncio
async def test_list_blobs(wrapper, session_faker):
    """
    Test pure list blobs.

    Args:
        wrapper: AzureBlobStorageWrapper
        session_faker: Faker
    """
    client_mock = MagicMock()

    properties = BlobProperties()
    properties.last_modified = datetime.datetime.now()
    properties.name = session_faker.word()

    expected_result = [properties]

    mock_list_blobs = MagicMock()
    mock_list_blobs.__aiter__.return_value = expected_result

    client_mock.list_blobs.return_value = mock_list_blobs

    wrapper._client = client_mock

    blobs = wrapper.list_blobs()
    result = []
    async for blob in blobs:
        result.append(blob)

    assert result == expected_result


@pytest.mark.asyncio
async def test_download_blob_without_file(wrapper, blob_content, session_faker):
    """
    Test get blob content.

    Args:
        wrapper: AzureBlobStorageWrapper
        blob_content: bytes
        session_faker: Faker
    """
    client_mock = MagicMock()

    blob_client = AsyncMock()
    mocked_stream = AsyncMock()
    mocked_stream.readall.return_value = blob_content

    blob_client.download_blob.return_value = mocked_stream

    client_mock.get_blob_client.return_value = blob_client

    wrapper._client = client_mock

    result = await wrapper.download_blob(session_faker.word(), False)

    assert result == (None, blob_content)


@pytest.mark.asyncio
async def test_download_blob_with_file(wrapper, blob_content, session_faker):
    """
    Test get blob content.

    Args:
        wrapper: AzureBlobStorageWrapper
        blob_content: bytes
        session_faker: Faker
    """
    client_mock = MagicMock()

    blob_client = AsyncMock()
    mocked_stream = AsyncMock()
    mocked_stream.chunks = MagicMock()
    mocked_stream.chunks.__aiter__.return_value = [blob_content]

    blob_client.download_blob.return_value = mocked_stream

    client_mock.get_blob_client.return_value = blob_client

    wrapper._client = client_mock

    result, _ = await wrapper.download_blob(session_faker.word(), True)

    assert result is not None

    os.remove(result)
