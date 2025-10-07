"""Tests for CrowdStrike Telemetry connector."""

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable
from unittest.mock import MagicMock

import aiofiles
import pytest
from connectors import AwsModule, AwsModuleConfiguration
from connectors.s3 import AwsS3QueuedConfiguration

from crowdstrike_telemetry.pull_telemetry_events import CrowdStrikeTelemetryConnector


@asynccontextmanager
async def async_temporary_file(data, mode="wb+"):
    async with aiofiles.tempfile.NamedTemporaryFile(mode) as f:
        await f.write(data)
        await f.seek(0)

        yield f


async def async_list(sequence: AsyncIterable[Any]) -> list[Any]:
    items = []
    async for item in sequence:
        items.append(item)

    return items


@pytest.fixture
def connector(session_faker, symphony_storage, mock_push_data_to_intakes) -> CrowdStrikeTelemetryConnector:
    """
    Create CrowdStrikeTelemetryConnector instance.

    Args:
        session_faker: Faker
        symphony_storage: str
        mock_push_data_to_intakes: AsyncMock

    Returns:
        CrowdStrikeTelemetryConnector:
    """
    module = AwsModule()
    module.configuration = AwsModuleConfiguration(
        aws_access_key=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region_name=session_faker.word(),
    )

    connector = CrowdStrikeTelemetryConnector(
        module=module,
        data_path=symphony_storage,
    )

    connector.configuration = AwsS3QueuedConfiguration(
        intake_server=session_faker.url(),
        queue_name=session_faker.word(),
        intake_key=session_faker.word(),
        chunk_size=session_faker.random.randint(1, 10),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
    )
    connector.push_events_to_intakes = MagicMock()
    connector.push_data_to_intakes = mock_push_data_to_intakes
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    return connector


@pytest.fixture
def test_data(session_faker) -> str:
    single_event = {"data": session_faker.sentence(), "event_simpleName": "EndOfProcess"}

    multiple_events = [
        {"data": session_faker.sentence(), "event_simpleName": "EndOfProcess"},
        {"data": session_faker.sentence(), "event_simpleName": "FalconServiceStatus"},
    ]

    return "\n".join([json.dumps(single_event)] + [json.dumps(event) for event in multiple_events])


@pytest.mark.asyncio
async def test_crowdstrike_parse_data(connector: CrowdStrikeTelemetryConnector, test_data: str):
    """
    Test CrowdStrikeTelemetryConnector `_parse_data`.

    Args:
        connector: CrowdStrikeTelemetryConnector
        test_data: bytes
    """

    async with async_temporary_file(test_data.encode("utf-8")) as f:
        assert await async_list(connector._parse_content(f)) == [
            line for line in test_data.split("\n") if line != "" and "FalconServiceStatus" not in line
        ]
