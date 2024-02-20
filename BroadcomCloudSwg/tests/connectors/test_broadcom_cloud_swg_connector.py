import os
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock

import pytest
from aioresponses import aioresponses
from faker import Faker
from sekoia_automation import constants

from connectors import BroadcomCloudModule, BroadcomCloudModuleConfig
from connectors.broadcom_cloud_swg_connector import BroadcomCloudSwgConnector, BroadcomCloudSwgConnectorConfig


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
def pushed_events_ids(session_faker: Faker) -> list[str]:
    """
    Generate random list of events ids.

    Args:
        session_faker: Faker

    Returns:
        list[str]:
    """
    return [session_faker.word() for _ in range(session_faker.random.randint(1, 10))]


@pytest.fixture
def connector(
    symphony_storage: Path,
    pushed_events_ids: list[str],
    session_faker: Faker,
) -> BroadcomCloudSwgConnector:
    """
    Creates BroadcomCloudSwgConnector.

    Args:
        symphony_storage: Path
        pushed_events_ids: list[str]
        session_faker: Faker

    Returns:

    """
    module = BroadcomCloudModule()

    connector = BroadcomCloudSwgConnector(
        module=module,
        data_path=symphony_storage,
    )

    connector.configuration = BroadcomCloudSwgConnectorConfig(
        intake_key=session_faker.word(),
    )

    # Mock the log function of trigger that requires network access to the api for reporting
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    # Mock the push_broadcom_data_to_intakes function
    connector.push_broadcom_data_to_intakes = AsyncMock(return_value=len(pushed_events_ids))

    connector.module.configuration = BroadcomCloudModuleConfig(
        username=session_faker.word(),
        password=session_faker.word(),
    )

    return connector


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_connector_last_event_date(connector: BroadcomCloudSwgConnector):
    """
    Test `last_event_date`.

    Args:
        connector: BroadcomCloudSwgConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.utcnow().replace(microsecond=0)
    one_hour_ago = current_date - timedelta(hours=1)

    assert connector.last_event_date == one_hour_ago

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.last_event_date == current_date

    one_day_ago = current_date - timedelta(days=1)
    with connector.context as cache:
        cache["last_event_date"] = (one_day_ago - timedelta(hours=6)).isoformat()

    assert connector.last_event_date == one_day_ago


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_connector_broadcom_client(connector: BroadcomCloudSwgConnector):
    """
    Test broadcom client initialization.

    Args:
        connector: BroadcomCloudSwgConnector
    """
    assert connector._broadcom_cloud_swg_client is None

    client1 = connector.broadcom_cloud_swg_client
    client2 = connector.broadcom_cloud_swg_client

    assert client1 is client2 is connector.broadcom_cloud_swg_client


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_connector_get_events(
    connector: BroadcomCloudSwgConnector, session_faker: Faker, logs_content: str, pushed_events_ids: list[str]
):
    """
    Test get_events.

    Args:
        connector: BroadcomCloudSwgConnector
        session_faker: Faker
        logs_content: str
        pushed_events_ids: list[str]
    """
    start_from = datetime.utcnow() - timedelta(minutes=session_faker.random.randint(1, 10))
    end_date = datetime.utcnow()

    with aioresponses() as mocked_responses:
        client = connector.broadcom_cloud_swg_client
        connector.broadcom_cloud_swg_client.base_url = session_faker.uri()
        with connector.context as cache:
            cache["last_event_date"] = start_from.isoformat()

        first_url = client.get_real_time_log_data_url(start_date=start_from, end_date=end_date, token=None)
        response_token = session_faker.word()

        file_name = "out.log"
        with open(file_name, "w") as file:
            file.write(logs_content)

        zip_file_name = "output.zip"
        with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(file_name)

        os.remove(file_name)

        with open(zip_file_name, "rb") as file:
            compressed_data = file.read()

        os.remove(zip_file_name)

        mocked_responses.get(
            first_url,
            status=200,
            body=compressed_data,
            headers={"X-sync-status": "more", "X-sync-token": response_token},
        )

        second_url = client.get_real_time_log_data_url(start_date=start_from, end_date=end_date, token=response_token)

        mocked_responses.get(
            second_url,
            status=200,
            body=compressed_data,
            headers={"X-sync-status": "done", "X-sync-token": session_faker.word()},
        )

        result, last_event_date = await connector.get_events()

        # Expect to push events to intakes 2 times
        expected_result = []
        expected_result.extend(pushed_events_ids)
        expected_result.extend(pushed_events_ids)

        assert len(expected_result) == result
