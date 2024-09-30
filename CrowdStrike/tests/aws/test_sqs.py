"""Test the SqsWrapper class."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from aws.sqs import SqsConfiguration, SqsWrapper


@pytest.fixture
def sqs_wrapper_configuration(session_faker) -> SqsConfiguration:
    """
    Create SqsConfiguration instance.

    Args:
        session_faker: Faker

    Returns:
        SqsConfiguration:
    """
    return SqsConfiguration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        queue_name=session_faker.word(),
        aws_region=session_faker.word(),
        intake_key=session_faker.word(),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
        is_fifo=False,
    )


@pytest.fixture
def sqs_wrapper_with_url_configuration(session_faker) -> SqsConfiguration:
    """
    Create SqsConfiguration instance that includes a url

    Args:
        session_faker: Faker

    Returns:
        SqsConfiguration:
    """
    return SqsConfiguration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        queue_name=session_faker.word(),
        queue_url=session_faker.url(),
        aws_region=session_faker.word(),
        intake_key=session_faker.word(),
        frequency=session_faker.random.randint(0, 20),
        delete_consumed_messages=True,
        is_fifo=False,
    )


@pytest.fixture
def sqs_wrapper(sqs_wrapper_configuration) -> SqsWrapper:
    """
    Create SqsWrapper instance.

    Args:
        sqs_wrapper_configuration: SqsConfiguration

    Returns:
        SqsWrapper:
    """
    return SqsWrapper(sqs_wrapper_configuration)


async def test_defined_queue_url(sqs_wrapper_with_url_configuration, session_faker):
    """
    Test the queue url provided in the module configuration is considered

    Args:
        sqs_wrapper: SqsWrapper
        sqs_wrapper_configuration: SqsConfiguration
        session_faker: Faker
    """
    sqs_wrapper = SqsWrapper(sqs_wrapper_with_url_configuration)

    with patch("aws.sqs.SqsWrapper.get_client") as mock_client:
        result_url = await sqs_wrapper.queue_url()

        assert sqs_wrapper_with_url_configuration.queue_url == result_url


@pytest.mark.asyncio
async def test_queue_url(sqs_wrapper, sqs_wrapper_configuration, session_faker):
    """
    Test queue_url property.

    Args:
        sqs_wrapper: SqsWrapper
        sqs_wrapper_configuration: SqsConfiguration
        session_faker: Faker
    """
    queue_url = session_faker.url()

    with patch("aws.sqs.SqsWrapper.get_client") as mock_client:
        mock_sqs = MagicMock()
        mock_sqs.get_queue_url = AsyncMock()
        mock_sqs.get_queue_url.return_value = {"QueueUrl": queue_url}

        mock_client.return_value.__aenter__.return_value = mock_sqs

        result_url = await sqs_wrapper.queue_url()

        assert queue_url == result_url

        mock_client.assert_called_once_with("sqs")
        mock_sqs.get_queue_url.assert_called_once_with(QueueName=sqs_wrapper_configuration.queue_name)


@pytest.mark.asyncio
async def test_receive_messages(sqs_wrapper, sqs_wrapper_configuration, session_faker):
    """
    Test receive_messages method.

    Args:
        sqs_wrapper: SqsWrapper
        sqs_wrapper_configuration: SqsConfiguration
        session_faker: Faker
    """
    first_message = session_faker.sentence()
    second_message = session_faker.sentence()

    receipt_handle_1 = session_faker.word()
    receipt_handle_2 = session_faker.word()

    queue_url = session_faker.url()

    expected_messages = [first_message, second_message]
    expected_response = {
        "Messages": [
            {"Body": first_message, "ReceiptHandle": receipt_handle_1},
            {"Body": second_message, "ReceiptHandle": receipt_handle_2},
        ]
    }

    with patch("aws.sqs.SqsWrapper.get_client") as mock_client:
        mock_sqs = MagicMock()

        mock_sqs.receive_message = AsyncMock()
        mock_sqs.receive_message.return_value = expected_response

        mock_sqs.delete_message = AsyncMock()
        mock_sqs.delete_message.return_value = {}

        mock_sqs.get_queue_url = AsyncMock()
        mock_sqs.get_queue_url.return_value = {"QueueUrl": queue_url}

        mock_client.return_value.__aenter__.return_value = mock_sqs

        async with sqs_wrapper.receive_messages(max_messages=6) as messages:
            assert messages == expected_messages

        mock_client.assert_has_calls([call("sqs")])
        mock_sqs.receive_message.assert_called_once_with(
            QueueUrl=queue_url,
            WaitTimeSeconds=sqs_wrapper_configuration.frequency,
            MaxNumberOfMessages=6,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
            VisibilityTimeout=60,
        )

        mock_sqs.delete_message.assert_any_call(QueueUrl=queue_url, ReceiptHandle=receipt_handle_1)
        mock_sqs.delete_message.assert_any_call(QueueUrl=queue_url, ReceiptHandle=receipt_handle_2)
