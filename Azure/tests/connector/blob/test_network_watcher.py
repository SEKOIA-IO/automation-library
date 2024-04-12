"""Tests related to connector."""

from datetime import datetime, timedelta, timezone
from gzip import GzipFile
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock

import aiofiles
import pytest
from azure.storage.blob import BlobProperties
from sekoia_automation.module import Module

from connectors.blob import AzureBlobConnectorConfig
from connectors.blob.azure_network_watcher import AzureNetworkWatcherConnector


@pytest.fixture
def connector(symphony_storage, container_name, account_name, account_key, session_faker, mock_push_data_to_intakes):
    module = Module()

    config = AzureBlobConnectorConfig(
        intake_key=session_faker.word(),
        container_name=container_name,
        account_name=account_name,
        account_key=account_key,
    )

    trigger = AzureNetworkWatcherConnector(
        module=module,
        data_path=symphony_storage,
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    trigger.push_data_to_intakes = mock_push_data_to_intakes

    trigger.configuration = config

    return trigger


@pytest.mark.asyncio
async def test_network_watcher_last_event_date(connector):
    """
    Test `last_event_date`.

    Args:
        connector: AzureNetworkWatcherConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    one_hour_ago = current_date - timedelta(hours=1)

    assert connector.last_event_date == one_hour_ago

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.last_event_date == current_date

    with connector.context as cache:
        cache["last_event_date"] = (one_hour_ago - timedelta(minutes=20)).isoformat()

    assert connector.last_event_date == one_hour_ago


@pytest.mark.asyncio
async def test_network_watcher_get_network_watcher_data_1(
    connector: AzureNetworkWatcherConnector, session_faker, blob_content
):
    """
    Test AzureNetworkWatcherConnector get events.

    Args:
        connector: AzureNetworkWatcherConnector
        session_faker: Faker
        blob_content: bytes
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date - timedelta(days=1)).isoformat()

    azure_blob_storage_wrapper = MagicMock()

    properties = BlobProperties()
    properties.last_modified = current_date
    properties.name = session_faker.word()

    expected_blobs = [properties]

    mock_list_blobs = MagicMock()
    mock_list_blobs.__aiter__.return_value = expected_blobs

    azure_blob_storage_wrapper.list_blobs.return_value = mock_list_blobs

    download_blob_result = AsyncMock()
    download_blob_result.return_value = (None, blob_content)

    azure_blob_storage_wrapper.download_blob = download_blob_result

    connector._azure_blob_storage_wrapper = azure_blob_storage_wrapper

    result = await connector.get_azure_blob_data()

    assert result == connector.filter_blob_data(blob_content.decode("utf-8"))


@pytest.mark.asyncio
async def test_network_watcher_get_network_watcher_data_2(
    connector: AzureNetworkWatcherConnector, session_faker, symphony_storage, blob_content
):
    """
    Test AzureNetworkWatcherConnector get events.

    Args:
        connector: AzureNetworkWatcherConnector
        session_faker: Faker
        symphony_storage: str
        blob_content: bytes
        pushed_events_ids: list[str]
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date - timedelta(days=1)).isoformat()

    async with aiofiles.tempfile.NamedTemporaryFile("wb", delete=False, dir="") as file:
        file_name = str(file.name)
        await file.write(blob_content)

    azure_blob_storage_wrapper = MagicMock()

    properties = BlobProperties()
    properties.last_modified = current_date
    properties.name = session_faker.word()

    expected_blobs = [properties]

    mock_list_blobs = MagicMock()
    mock_list_blobs.__aiter__.return_value = expected_blobs

    azure_blob_storage_wrapper.list_blobs.return_value = mock_list_blobs

    download_blob_result = AsyncMock()
    download_blob_result.return_value = (file_name, None)

    azure_blob_storage_wrapper.download_blob = download_blob_result

    connector._azure_blob_storage_wrapper = azure_blob_storage_wrapper

    result = await connector.get_azure_blob_data()

    assert result == connector.filter_blob_data(blob_content.decode("utf-8"))


@pytest.mark.asyncio
async def test_network_watcher_get_network_watcher_data_3(
    connector: AzureNetworkWatcherConnector, session_faker, symphony_storage, blob_content
):
    """
    Test AzureNetworkWatcherConnector get events.

    Args:
        connector: AzureNetworkWatcherConnector
        session_faker: Faker
        symphony_storage: str
        blob_content: bytes
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)

    # Try to put last event date higher to be 1 day ahead of the log file date
    with connector.context as cache:
        cache["last_event_date"] = (current_date - timedelta(days=1)).isoformat()

    with NamedTemporaryFile("wb", delete=False, dir="") as file, GzipFile(fileobj=file, mode="w+") as gfile:
        file_name = str(file.name)
        gfile.write(blob_content)

    azure_blob_storage_wrapper = MagicMock()

    properties = BlobProperties()
    properties.last_modified = current_date
    properties.name = session_faker.word()

    expected_blobs = [properties]

    mock_list_blobs = MagicMock()
    mock_list_blobs.__aiter__.return_value = expected_blobs

    azure_blob_storage_wrapper.list_blobs.return_value = mock_list_blobs

    download_blob_result = AsyncMock()
    download_blob_result.return_value = (file_name, None)

    azure_blob_storage_wrapper.download_blob = download_blob_result

    connector._azure_blob_storage_wrapper = azure_blob_storage_wrapper

    result = await connector.get_azure_blob_data()

    assert result == connector.filter_blob_data(blob_content.decode("utf-8"))
