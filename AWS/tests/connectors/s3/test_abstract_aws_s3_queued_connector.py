"""Contains tests for AbstractAwsS3QueuedConnector."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock

import io
import orjson
import pytest
from faker import Faker

from aws_helpers.s3_wrapper import S3Wrapper
from aws_helpers.sqs_wrapper import SqsWrapper
from connectors import AwsModule
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration
from tests.helpers import async_bytesIO, async_list, async_temporary_file


@pytest.fixture
def test_bucket(session_faker: Faker) -> str:
    """
    Create a test bucket.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def test_key(session_faker: Faker) -> str:
    """
    Create a test key.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def sqs_message(test_bucket: str, test_key: str) -> str:
    """
    Create a SQS message with necessary bucket and key.

    Args:
        test_bucket: str
        test_key: str

    Returns:
        str:
    """
    return (
        '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"eu-west-2",'
        '"eventTime":"2022-06-27T16:17:56.712Z","eventName":"ObjectCreated:Put","userIdentity":{'
        '"principalId":"AWS:AROAJ6N5EQDKQTHMBI5GS:regionalDeliverySession"},"requestParameters":{'
        '"sourceIPAddress":"52.56.67.70"},"responseElements":{"x-amz-request-id":"D4M2F8DTSQVJRX7C",'
        '"x-amz-id-2":"HFot7T6fvHiCaoyE2K/J/uRDPqoDlYOE8vBGZmc/I9Wc+U7RgOrA4qYLaxjbPEnCb1XW4MnrOQ8'
        '+AZoCeBJVR53QY1UEN4VT"},"s3":{"s3SchemaVersion":"1.0","configurationId":"FlowLogs","bucket":{'
        f'"name":"{test_bucket}"'
        ',"ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},'
        '"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{'
        f'"key":"{test_key}",'
        '"size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}'
    )


@pytest.fixture
def abstract_queued_connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
    mock_push_data_to_intakes: AsyncMock,
) -> AbstractAwsS3QueuedConnector:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_queued_config: AwsS3QueuedConfiguration
        mock_push_data_to_intakes: AsyncMock

    Returns:
        AbstractAwsS3QueuedConnector:
    """
    os.environ["AWS_BATCH_SIZE"] = "1"
    connector = AbstractAwsS3QueuedConnector(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_queued_config

    connector.push_data_to_intakes = mock_push_data_to_intakes

    async def _parse_content(stream: BinaryIO) -> AsyncGenerator[str, None]:
        """
        Parse the content of a S3 object

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


def test_abstract_aws_s3_queued_connector_wrappers(abstract_queued_connector: AbstractAwsS3QueuedConnector):
    """
    Test AbstractAwsS3QueuedConnector s3 wrapper initialization.

    Args:
        abstract_queued_connector: AbstractAwsS3QueuedConnector
    """
    assert isinstance(abstract_queued_connector.s3_wrapper, S3Wrapper)
    assert isinstance(abstract_queued_connector.sqs_wrapper, SqsWrapper)


@pytest.mark.asyncio
async def test_abstract_aws_s3_queued_connector_next_batch(
    session_faker: Faker, abstract_queued_connector: AbstractAwsS3QueuedConnector, sqs_message: str
):
    """
    Test AbstractAwsS3QueuedConnector next_batch method.

    Args:
        session_faker: Faker
        abstract_queued_connector: AbstractAwsS3QueuedConnector
        sqs_message: str
    """
    amount_of_messages = session_faker.pyint(min_value=5, max_value=100)

    sqs_messages = [(sqs_message, session_faker.pyint(min_value=5, max_value=100)) for _ in range(amount_of_messages)]

    expected_timestamps = []
    for data in sqs_messages:
        _, timestamp = data

        expected_timestamps.append(timestamp)

    data_content = session_faker.word()
    expected_result = [data_content for _ in range(amount_of_messages)]

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    abstract_queued_connector.sqs_wrapper = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = sqs_messages

    abstract_queued_connector.s3_wrapper = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key.return_value.__aenter__.side_effect = read_key

    result = await abstract_queued_connector.next_batch()

    assert result[0] == len(expected_result)
    assert len(result[1]) == len(expected_timestamps)
    assert result == (len(expected_result), expected_timestamps)


async def test_abstract_aws_s3_queued_connector_next_batch_with_errored_message(
    session_faker: Faker, abstract_queued_connector: AbstractAwsS3QueuedConnector, sqs_message: str
):
    """
    Test AbstractAwsS3QueuedConnector next_batch method.

    Args:
        session_faker: Faker
        abstract_queued_connector: AbstractAwsS3QueuedConnector
        sqs_message: str
    """
    amount_of_messages = session_faker.pyint(min_value=5, max_value=100)

    valid_messages = [
        (sqs_message, session_faker.pyint(min_value=1, max_value=1000)) for _ in range(amount_of_messages)
    ] + [(session_faker.word(), session_faker.pyint(min_value=1, max_value=1000))]

    expected_timestamps = []
    for data in valid_messages:
        message, timestamp = data

        expected_timestamps.append(timestamp)

    data_content = session_faker.word()
    expected_result = [data_content for _ in range(amount_of_messages)]

    abstract_queued_connector.sqs_wrapper = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = valid_messages

    async def read_key():
        return await async_bytesIO(data_content.encode("utf-8"))

    abstract_queued_connector.s3_wrapper = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key.return_value.__aenter__.side_effect = read_key

    result = await abstract_queued_connector.next_batch()

    assert result[0] == len(expected_result)
    assert len(result[1]) == len(expected_timestamps)
    assert result == (len(expected_result), expected_timestamps)


async def test_abstract_aws_s3_queued_connector_next_batch_with_errored_message_1(
    session_faker: Faker,
    abstract_queued_connector: AbstractAwsS3QueuedConnector,
):
    """
    Test AbstractAwsS3QueuedConnector next_batch method.

    Args:
        session_faker: Faker
        abstract_queued_connector: AbstractAwsS3QueuedConnector
    """
    sqs_message = orjson.dumps({"Records": [{}]}).decode("utf-8")
    message_timestamp = session_faker.pyint(min_value=1, max_value=1000)
    sqs_messages = [(sqs_message, message_timestamp)]

    abstract_queued_connector.sqs_wrapper = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = sqs_messages

    result = await abstract_queued_connector.next_batch()

    assert result == (0, [message_timestamp])


async def test_abstract_aws_s3_queued_connector_next_batch_with_errored_message_2(
    session_faker: Faker,
    abstract_queued_connector: AbstractAwsS3QueuedConnector,
):
    """
    Test AbstractAwsS3QueuedConnector next_batch method.

    Args:
        session_faker: Faker
        abstract_queued_connector: AbstractAwsS3QueuedConnector
    """
    sqs_message = orjson.dumps({"Records": [{"s3": {"bucket": {"name": session_faker.word()}}}]}).decode("utf-8")
    message_timestamp = session_faker.pyint(min_value=1, max_value=1000)
    sqs_messages = [(sqs_message, message_timestamp)]

    abstract_queued_connector.sqs_wrapper = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = sqs_messages

    result = await abstract_queued_connector.next_batch()

    assert result == (0, [message_timestamp])


async def test_abstract_aws_s3_queued_connector_next_batch_with_empty_data_in_s3(
    session_faker: Faker, abstract_queued_connector: AbstractAwsS3QueuedConnector, sqs_message: str
):
    """
    Test AbstractAwsS3QueuedConnector next_batch method.

    Args:
        session_faker: Faker
        abstract_queued_connector: AbstractAwsS3QueuedConnector
        sqs_message: str
    """
    amount_of_messages = session_faker.pyint(min_value=5, max_value=100)

    valid_messages = [
        (sqs_message, session_faker.pyint(min_value=1, max_value=1000)) for _ in range(amount_of_messages)
    ]

    abstract_queued_connector.sqs_wrapper = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages = MagicMock()
    abstract_queued_connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = valid_messages

    abstract_queued_connector.s3_wrapper = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key = MagicMock()
    abstract_queued_connector.s3_wrapper.read_key.return_value.__aenter__.return_value = b""

    result = await abstract_queued_connector.next_batch()

    assert result == (0, [message[1] for message in valid_messages])
