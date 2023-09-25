"""Tests related to connector."""
from datetime import datetime, timedelta, timezone
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock

import aiofiles
import pytest
from azure.storage.blob import BlobProperties
from sekoia_automation import constants

from connector import AzureBlobStorageModule
from connector.pull_azure_blob_data import AzureBlobConnector, AzureBlobConnectorConfig


@pytest.fixture
def symphony_storage() -> str:
    """
    Fixture for symphony temporary storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture
def pushed_events_ids(session_faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker

    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def connector(symphony_storage, container_name, account_name, account_key, pushed_events_ids, session_faker):
    module = AzureBlobStorageModule()
    config = AzureBlobConnectorConfig(
        intake_key=session_faker.word(),
    )

    trigger = AzureBlobConnector(
        module=module,
        data_path=symphony_storage,
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    # Mock the push_events_to_intakes function
    trigger.push_events_to_intakes = MagicMock()
    trigger.push_events_to_intakes.return_value = pushed_events_ids

    trigger.push_data_to_intakes = AsyncMock(return_value=pushed_events_ids)

    trigger.module.configuration = {
        "container_name": container_name,
        "account_name": account_name,
        "account_key": account_key,
    }

    trigger.configuration = config

    return trigger


@pytest.mark.asyncio
async def test_azure_blob_connector_last_event_date(connector):
    """
    Test `last_event_date`.

    Args:
        connector: AzureBlobConnector
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
async def test_azure_blob_get_azure_blob_data_1(
    connector: AzureBlobConnector, session_faker, blob_content, pushed_events_ids
):
    """
    Test AzureBlobConnector get events.

    Args:
        connector: AzureBlobConnector
        session_faker: Faker
        blob_content: bytes
        pushed_events_ids: list[str]
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

    assert result == pushed_events_ids


@pytest.mark.asyncio
async def test_azure_blob_get_azure_blob_data_2(
    connector: AzureBlobConnector, session_faker, symphony_storage, blob_content, pushed_events_ids
):
    """
    Test AzureBlobConnector get events.

    Args:
        connector: AzureBlobConnector
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

    assert result == pushed_events_ids
