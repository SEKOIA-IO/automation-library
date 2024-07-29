import asyncio
import os
import zipfile
from asyncio import Queue
from datetime import datetime, timedelta
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytz
from aioresponses import aioresponses
from faker import Faker
from sekoia_automation import constants

from connectors import BroadcomCloudModule, BroadcomCloudModuleConfig
from connectors.broadcom_cloud_swg_connector import (
    BroadcomCloudSwgConnector,
    BroadcomCloudSwgConnectorConfig,
    DatetimeRange,
)


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
def mock_push_data_to_intakes() -> AsyncMock:
    """
    Mocked push_data_to_intakes method.

    Returns:
        AsyncMock:
    """

    def side_effect_return_input(events: list[str]) -> list[str]:
        """
        Return input value.

        Uses in side_effect to return input value from mocked function.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return events

    return AsyncMock(side_effect=side_effect_return_input)


@pytest.fixture
def connector(
    symphony_storage: Path,
    pushed_events_ids: list[str],
    session_faker: Faker,
    mock_push_data_to_intakes: AsyncMock,
) -> BroadcomCloudSwgConnector:
    """
    Creates BroadcomCloudSwgConnector.

    Args:
        symphony_storage: Path
        pushed_events_ids: list[str]
        session_faker: Faker
        mock_push_data_to_intakes: AsyncMock

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
    connector.push_data_to_intakes = mock_push_data_to_intakes

    connector.module.configuration = BroadcomCloudModuleConfig(
        username=session_faker.word(),
        password=session_faker.word(),
    )

    return connector


@pytest.mark.asyncio
async def test_broadcom_cloud_swg_connector_work_with_latest_offsets(connector: BroadcomCloudSwgConnector):
    """
    Test `get_latest_offsets`.

    Args:
        connector: BroadcomCloudSwgConnector
    """
    with connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(pytz.utc).replace(microsecond=0)

    assert connector.get_latest_offsets == {}

    with connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert connector.get_latest_offsets == {
        int(current_date.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            end_date=current_date
        )
    }

    first_value = current_date - timedelta(hours=2)
    second_value = current_date - timedelta(hours=3)
    third_value = current_date - timedelta(hours=4)
    fourth_value = current_date - timedelta(hours=5)

    with connector.context as cache:
        cache["offsets"] = {
            str(int(first_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)): {
                "start_date": first_value.isoformat(),
                "end_date": second_value.isoformat(),
            },
            str(int(second_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)): {
                "start_date": second_value.isoformat(),
                "end_date": third_value.isoformat(),
            },
        }

    assert connector.get_latest_offsets == {
        int(current_date.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            end_date=current_date
        ),
        int(first_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": first_value,
                "end_date": second_value,
            }
        ),
        int(second_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": second_value,
                "end_date": third_value,
            }
        ),
    }

    with connector.context as cache:
        cache["last_event_date"] = None

    assert connector.get_latest_offsets == {
        int(first_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": first_value,
                "end_date": second_value,
            }
        ),
        int(second_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": second_value,
                "end_date": third_value,
            }
        ),
    }

    new_offsets = {
        int(second_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": third_value,
                "end_date": fourth_value,
            }
        ),
        int(fourth_value.replace(minute=0, second=0, microsecond=0).timestamp() * 1000): DatetimeRange(
            **{
                "start_date": second_value,
                "end_date": fourth_value,
            }
        ),
    }

    connector.update_latest_offsets(new_offsets)

    assert connector.get_latest_offsets == new_offsets


@pytest.mark.asyncio
async def test_produce_file_to_queue(
    connector: BroadcomCloudSwgConnector,
    session_faker: Faker,
    logs_content: str,
):
    queue = Queue()
    file_name = "{0}.log".format(session_faker.word())
    with open(file_name, "w") as file:
        file.write(logs_content)

    zip_file_name = "{0}.zip".format(session_faker.word())
    with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(file_name)

    os.remove(file_name)

    result = await asyncio.gather(
        connector.produce_file_to_queue(zip_file_name, queue, DatetimeRange()), connector.consume_file_events(queue)
    )

    os.remove(zip_file_name)

    assert result[0] == DatetimeRange()
    assert result[1] == len([line for line in logs_content.split("\n") if not line.startswith("#")])


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
    start_from = datetime.now(pytz.utc) - timedelta(minutes=session_faker.random.randint(1, 10))

    with aioresponses() as mocked_responses:
        client = connector.broadcom_cloud_swg_client
        connector.broadcom_cloud_swg_client.base_url = session_faker.uri()
        with connector.context as cache:
            cache["last_event_date"] = start_from.isoformat()

        first_url, _ = client.get_real_time_log_data_url(start_date=start_from)
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

        second_url, _ = client.get_real_time_log_data_url(
            start_date=start_from - timedelta(hours=1),
        )

        mocked_responses.get(
            second_url,
            status=200,
            body=compressed_data,
            headers={"X-sync-status": "done", "X-sync-token": session_faker.word()},
        )

        third_file_id = int(
            (start_from - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0).timestamp() * 1000
        )
        third_url = client.download_file_url([third_file_id])

        mocked_responses.get(
            third_url,
            status=200,
            body=compressed_data,
            headers={"X-sync-status": "done", "X-sync-token": session_faker.word()},
        )

        list_of_files_url = client.list_of_files_to_process_url(
            start_from - timedelta(hours=4),
            start_from - timedelta(hours=2),
        )

        mocked_responses.get(
            list_of_files_url,
            status=200,
            payload={"items": [{"date": third_file_id}]},
            headers={"X-sync-status": "done", "X-sync-token": session_faker.word()},
        )

        with connector.context as cache:
            cache["offsets"] = {
                str(
                    int(
                        (start_from - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0).timestamp() * 1000
                    )
                ): {},
                str(
                    int(
                        (start_from - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).timestamp() * 1000
                    )
                ): {},
            }

        result, last_event_date = await connector.get_events()

        # Expect to push events to intakes 3 times
        expected_result = []
        expected_result.extend(logs_content.split("\n"))
        expected_result.extend(logs_content.split("\n"))
        expected_result.extend(logs_content.split("\n"))

        assert len([v for v in expected_result if not v.startswith("#")]) == result
