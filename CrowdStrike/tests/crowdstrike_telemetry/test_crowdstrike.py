"""Tests for CrowdStrike Telemetry connector."""

import asyncio
import io
import json
from concurrent.futures import Executor
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, AsyncIterable
from unittest.mock import MagicMock

import aiofiles
import orjson
import pytest
from aiofiles.threadpool.binary import AsyncBufferedReader

from crowdstrike_telemetry import CrowdStrikeTelemetryModule
from crowdstrike_telemetry.pull_telemetry_events import (
    CrowdStrikeTelemetryConnector,
    CrowdStrikeTelemetryConnectorConfig,
)


async def async_bytesIO(
    data: bytes,
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    executor: Executor | None = None,
) -> Any:
    if loop is None:
        loop = asyncio.get_running_loop()

    cb = partial(
        io.BytesIO,
        data,
    )
    f = await loop.run_in_executor(executor, cb)
    return AsyncBufferedReader(f, loop=loop, executor=executor)


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
    module = CrowdStrikeTelemetryModule()
    # In order to support backward compatibility test the aliases
    module.configuration = {
        "aws_secret_access_key": session_faker.word(),
        "aws_access_key_id": session_faker.word(),
        "aws_region": session_faker.word(),
    }

    connector = CrowdStrikeTelemetryConnector(
        module=module,
        data_path=symphony_storage,
    )

    connector.configuration = CrowdStrikeTelemetryConnectorConfig(
        intake_server=session_faker.url(),
        # queue_name=session_faker.word(),
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


@pytest.fixture
def sqs_message(session_faker) -> str:
    return orjson.dumps(
        {
            "cid": session_faker.uuid4(),
            "timestamp": 1662307838018,
            "fileCount": 1,
            "totalSize": 13090,
            "bucket": "bucket-name",
            "pathPrefix": "path-prefix",
            "files": [{"path": "path-to-file", "size": 13090, "checksum": "checksum"}],
        }
    ).decode("utf-8")


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


@pytest.mark.asyncio
async def test_crowdstrike_next_batch(
    session_faker: Any, sqs_message: dict[str, Any], test_data: str, connector: CrowdStrikeTelemetryConnector
):
    """
    Test trigger CrowdStrikeTelemetryConnector with expected all messages to decode.

    Args:
        session_faker: Faker
        sqs_message: str
        connector: CrowdStrikeTelemetryConnector
    """
    amount_of_messages = session_faker.pyint(min_value=5, max_value=100)

    messages = [(sqs_message, session_faker.pyint(min_value=1, max_value=1000)) for _ in range(amount_of_messages)]

    async def read_key():
        return await async_bytesIO(test_data.encode("utf-8"))

    connector.limit_of_events_to_push = 1  # to test multiple iterations of the loop

    connector.sqs_wrapper = MagicMock()
    connector.sqs_wrapper.receive_messages = MagicMock()
    connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = messages

    connector.s3_wrapper = MagicMock()
    connector.s3_wrapper.read_key = MagicMock()
    connector.s3_wrapper.read_key.return_value.__aenter__.side_effect = read_key

    total_events, times_to_log = await connector.next_batch()

    assert total_events == amount_of_messages * 2  # 2 events in test_data
