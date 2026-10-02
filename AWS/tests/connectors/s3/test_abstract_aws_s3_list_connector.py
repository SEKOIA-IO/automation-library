"""Contains tests for AbstractAwsS3ListConnector."""

import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from faker import Faker

from aws_helpers.s3_wrapper import S3Wrapper
from connectors import AwsModule
from connectors.s3 import AbstractAwsS3ListConnector, AwsS3ListConfiguration
from connectors.s3.provider import AwsAccountProvider
from tests.helpers import async_bytesIO


@pytest.fixture
def aws_s3_list_config(faker: Faker) -> AwsS3ListConfiguration:
    """
    Create a connector configuration.

    Args:
        faker: Faker

    Returns:
        AwsS3ListConfiguration:
    """
    return AwsS3ListConfiguration(
        intake_key=faker.word(),
        bucket=faker.word(),
    )


@pytest.fixture
def abstract_list_connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_list_config: AwsS3ListConfiguration,
    mock_push_data_to_intakes: AsyncMock,
) -> AbstractAwsS3ListConnector:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_list_config: AwsS3ListConfiguration
        mock_push_data_to_intakes: AsyncMock

    Returns:
        AbstractAwsS3ListConnector:
    """
    os.environ["AWS_BATCH_SIZE"] = "1"
    klass = type("TestAbstractAwsS3ListConnector", (AbstractAwsS3ListConnector, AwsAccountProvider), {})
    connector = klass(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_list_config
    connector.push_data_to_intakes = mock_push_data_to_intakes

    async def _parse_content(stream: BinaryIO) -> AsyncGenerator[str, None]:
        """
        Parse the content of a S3 object.

        Args:
            stream: BinaryIO
        """
        content = await stream.read()
        result = content.decode("utf-8")
        if result:
            yield result

    connector._parse_content = MagicMock(side_effect=_parse_content)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    return connector


def test_abstract_aws_s3_list_connector_wrappers(abstract_list_connector: AbstractAwsS3ListConnector):
    """
    Test AbstractAwsS3ListConnector s3 wrapper initialization.

    Args:
        abstract_list_connector: AbstractAwsS3ListConnector
    """
    assert isinstance(abstract_list_connector.s3_wrapper, S3Wrapper)


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch(
    session_faker: Faker,
    abstract_list_connector: AbstractAwsS3ListConnector,
):
    """
    Test AbstractAwsS3ListConnector next_batch processes all objects and returns correct count/timestamps.

    Args:
        session_faker: Faker
        abstract_list_connector: AbstractAwsS3ListConnector
    """
    amount_of_objects = session_faker.pyint(min_value=2, max_value=10)
    data_content = session_faker.word()
    now = datetime.now(timezone.utc)

    s3_objects = [{"Key": f"file-{i}.log", "Size": 100, "LastModified": now} for i in range(amount_of_objects)]

    async def list_objects(bucket=None, prefix=None, start_after=None):
        for obj in s3_objects:
            yield obj

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects
    mock_s3.read_key = MagicMock()
    mock_s3.read_key.return_value.__aenter__.side_effect = read_key

    connector_type = type(abstract_list_connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        result = await abstract_list_connector.next_batch()

    assert result[0] == amount_of_objects
    assert len(result[1]) == amount_of_objects


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch_writes_marker(
    session_faker: Faker,
    abstract_list_connector: AbstractAwsS3ListConnector,
):
    """
    Test that the marker is written to the last processed object key after all objects are processed.

    Args:
        session_faker: Faker
        abstract_list_connector: AbstractAwsS3ListConnector
    """
    data_content = session_faker.word()
    last_key = "file-2.log"
    s3_objects = [
        {"Key": "file-0.log", "Size": 100},
        {"Key": "file-1.log", "Size": 100},
        {"Key": last_key, "Size": 100},
    ]

    async def list_objects(bucket=None, prefix=None, start_after=None):
        for obj in s3_objects:
            yield obj

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects
    mock_s3.read_key = MagicMock()
    mock_s3.read_key.return_value.__aenter__.side_effect = read_key

    connector_type = type(abstract_list_connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        await abstract_list_connector.next_batch()

    assert abstract_list_connector.read_marker() == last_key


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch_uses_existing_marker(
    session_faker: Faker,
    abstract_list_connector: AbstractAwsS3ListConnector,
):
    """
    Test that an existing marker is passed as start_after to list_objects.

    Args:
        session_faker: Faker
        abstract_list_connector: AbstractAwsS3ListConnector
    """
    existing_marker = "previous-file.log"
    abstract_list_connector.write_marker(existing_marker)

    data_content = session_faker.word()
    received_start_after: list[str | None] = []

    async def list_objects(bucket=None, prefix=None, start_after=None):
        received_start_after.append(start_after)
        yield {"Key": "file-1.log", "Size": 100}

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects
    mock_s3.read_key = MagicMock()
    mock_s3.read_key.return_value.__aenter__.side_effect = read_key

    connector_type = type(abstract_list_connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        await abstract_list_connector.next_batch()

    assert received_start_after == [existing_marker]


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch_error_stops_loop(
    session_faker: Faker,
    abstract_list_connector: AbstractAwsS3ListConnector,
):
    """
    Test that an exception on one object stops the loop and does not advance the marker.

    Args:
        session_faker: Faker
        abstract_list_connector: AbstractAwsS3ListConnector
    """
    data_content = session_faker.word()
    good_key = "file-0.log"
    bad_key = "file-1.log"

    s3_objects = [
        {"Key": good_key, "Size": 100},
        {"Key": bad_key, "Size": 100},
        {"Key": "file-2.log", "Size": 100},
    ]

    async def list_objects(bucket=None, prefix=None, start_after=None):
        for obj in s3_objects:
            yield obj

    call_count = [0]

    async def read_key():
        call_count[0] += 1
        if call_count[0] >= 2:
            raise Exception("S3 read error")
        return await async_bytesIO(data_content.encode("utf-8"))

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects
    mock_s3.read_key = MagicMock()
    mock_s3.read_key.return_value.__aenter__.side_effect = read_key

    connector_type = type(abstract_list_connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        result = await abstract_list_connector.next_batch()

    # Only the first (good) object was successfully processed
    assert result[0] == 1
    # The marker should not be advanced past the successfully processed key
    assert abstract_list_connector.read_marker() == good_key
    # file-2.log should not have been read (loop stopped after error)
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch_mid_batch_flush(
    session_faker: Faker,
    aws_module: AwsModule,
    symphony_storage: Path,
    mock_push_data_to_intakes: AsyncMock,
):
    """
    Test that a mid-batch flush occurs and the marker is written when records reach the limit.

    Args:
        session_faker: Faker
        aws_module: AwsModule
        symphony_storage: Path
        mock_push_data_to_intakes: AsyncMock
    """
    bucket_name = session_faker.word()
    config = AwsS3ListConfiguration(
        intake_key=session_faker.word(),
        bucket=bucket_name,
    )

    klass = type("TestAbstractAwsS3ListConnector", (AbstractAwsS3ListConnector, AwsAccountProvider), {})
    connector = klass(module=aws_module, data_path=symphony_storage)
    connector.configuration = config
    connector.push_data_to_intakes = mock_push_data_to_intakes
    # Set a batch limit of 2 so mid-batch flush triggers after the second object
    connector.limit_of_events_to_push = 2

    data_content = session_faker.word()
    flush_key = "file-1.log"

    s3_objects = [
        {"Key": "file-0.log", "Size": 100},
        {"Key": flush_key, "Size": 100},
        {"Key": "file-2.log", "Size": 100},
    ]

    async def _parse_content(stream: BinaryIO) -> AsyncGenerator[str, None]:
        content = await stream.read()
        result = content.decode("utf-8")
        if result:
            yield result

    connector._parse_content = MagicMock(side_effect=_parse_content)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()

    async def list_objects(bucket=None, prefix=None, start_after=None):
        for obj in s3_objects:
            yield obj

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects
    mock_s3.read_key = MagicMock()
    mock_s3.read_key.return_value.__aenter__.side_effect = read_key

    connector_type = type(connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        result = await connector.next_batch()

    # All 3 objects were processed
    assert result[0] == 3
    # push_data_to_intakes was called twice: once at mid-batch (2 records) and once at end (1 record)
    assert mock_push_data_to_intakes.call_count == 2
    # Marker reflects the last processed object
    assert connector.read_marker() == "file-2.log"


@pytest.mark.asyncio
async def test_abstract_aws_s3_list_connector_next_batch_no_objects(
    session_faker: Faker,
    abstract_list_connector: AbstractAwsS3ListConnector,
):
    """
    Test that next_batch returns zero events and empty timestamps when the bucket is empty.

    Args:
        session_faker: Faker
        abstract_list_connector: AbstractAwsS3ListConnector
    """

    async def list_objects(bucket=None, prefix=None, start_after=None):
        return
        yield  # make it an async generator

    mock_s3 = MagicMock()
    mock_s3.list_objects = list_objects

    connector_type = type(abstract_list_connector)
    with patch.object(connector_type, "s3_wrapper", new_callable=PropertyMock, return_value=mock_s3):
        result = await abstract_list_connector.next_batch()

    assert result == (0, [])
    assert abstract_list_connector.read_marker() is None
