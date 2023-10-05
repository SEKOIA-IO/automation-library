"""Contains tests for AwsSqsMessagesTrigger."""
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from faker import Faker

from aws_helpers.sqs_wrapper import SqsWrapper
from connectors import AwsModule
from connectors.trigger_sqs_messages import AwsSqsMessagesTrigger, AwsSqsMessagesTriggerConfiguration


@pytest.fixture
def sqs_message() -> bytes:
    """
    Contains sqs message example.

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
        '"name":"aws-cloudtrail-111111111111-3abc4c4f","ownerIdentity":{"principalId":"A2ZXD4XGWPNOQ9"},'
        '"arn":"arn:aws:s3:::aws-cloudtrail-111111111111-3abc4c4f"},"object":{'
        '"key":"AWSLogs/aws-account-id=111111111111/aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month'
        '=08/day=31/111111111111_vpcflowlogs_eu-west-3_fl-032a163fae170ae52_20220831T1255Z_2ad4bef5.log.parquet",'
        '"size":9234,"eTag":"0cdef8885755dff42b6fbd91732ae506","sequencer":"0062B9D834A809629F"}}}]}'
    )


@pytest.fixture
def connector_config(faker: Faker, intake_key: str) -> AwsSqsMessagesTriggerConfiguration:
    """
    Create a connector configuration.

    Args:
        faker: Faker
        intake_key: str

    Returns:
        AwsSqsMessagesTriggerConfiguration:
    """
    return AwsSqsMessagesTriggerConfiguration(
        intake_key=intake_key,
        frequency=faker.pyint(),
        queue_name=faker.word(),
    )


@pytest.fixture
def connector(
    aws_module: AwsModule,
    connector_config: AwsSqsMessagesTriggerConfiguration,
    mock_push_data_to_intakes: AsyncMock,
) -> AwsSqsMessagesTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        connector_config: AwsSqsMessagesTriggerConfiguration
        mock_push_data_to_intakes: AsyncMock

    Returns:
        AwsSqsMessagesTrigger:
    """
    connector = AwsSqsMessagesTrigger()

    connector.module = aws_module
    connector.configuration = connector_config

    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_trigger_sqs_messages_client(
    aws_module: AwsModule, connector_config: AwsSqsMessagesTriggerConfiguration
):
    """
    Test trigger SQS messages sqs wrapper initialization.

    Args:
        aws_module: AwsModule
        connector_config: AwsSqsMessagesTriggerConfiguration
    """
    connector = AwsSqsMessagesTrigger()

    connector.module = aws_module
    connector.configuration = connector_config

    assert isinstance(connector.sqs_wrapper, SqsWrapper)


@pytest.mark.asyncio
async def test_trigger_sqs_messages(faker: Faker, sqs_message: str, connector: AwsSqsMessagesTrigger):
    """
    Test trigger AwsSqsMessagesTriggerConfiguration.

    Args:
        faker: Faker
        sqs_message: str
        connector: AwsSqsMessagesTrigger
    """
    amount_of_messages = faker.pyint(min_value=5, max_value=100)

    valid_messages = [sqs_message for _ in range(amount_of_messages)]
    expected_result = []
    for message in valid_messages:
        expected_result.extend(orjson.loads(message).get("Records", []))

    connector.sqs_wrapper = MagicMock()
    connector.sqs_wrapper.receive_messages = MagicMock()
    connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = valid_messages

    assert await connector.next_batch() == expected_result


@pytest.mark.asyncio
async def test_trigger_sqs_messages_with_one_failed(faker: Faker, sqs_message: str, connector: AwsSqsMessagesTrigger):
    """
    Test trigger AwsSqsMessagesTriggerConfiguration with expected one failed message to decode.

    Args:
        faker: Faker
        sqs_message: str
        connector: AwsSqsMessagesTrigger
    """
    amount_of_messages = faker.pyint()

    valid_messages = [sqs_message for _ in range(amount_of_messages)]
    expected_result = []
    for message in valid_messages:
        expected_result.extend(orjson.loads(message).get("Records", []))

    connector.sqs_wrapper = MagicMock()
    connector.sqs_wrapper.receive_messages = MagicMock()
    connector.sqs_wrapper.receive_messages.return_value.__aenter__.return_value = valid_messages + [faker.word()]

    assert await connector.next_batch() == expected_result
