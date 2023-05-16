"""Test the SqsWrapper class."""
from unittest.mock import patch

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
        chunk_size=session_faker.random.randint(1, 10),
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


@pytest.mark.asyncio
async def test_queue_url(sqs_wrapper, sqs_wrapper_configuration, session_faker):
    """
    Test queue_url property.

    Args:
        sqs_wrapper: SqssWrapper
        sqs_wrapper_configuration: SqsConfiguration
        session_faker: Faker
    """
    queue_url = session_faker.url()
    with patch.object(sqs_wrapper._sqs, "get_queue_url") as mock_get_queue_url:
        mock_get_queue_url.return_value = {"QueueUrl": queue_url}

        queue_url = sqs_wrapper.queue_url

        assert queue_url == queue_url
        mock_get_queue_url.assert_called_once_with(QueueName=sqs_wrapper_configuration.queue_name)


@pytest.mark.asyncio
async def test_receive_messages(sqs_wrapper, sqs_wrapper_configuration, session_faker):
    """
    Test receive_messages method.

    Args:
        sqs_wrapper: SqsWrapper
        sqs_wrapper_configuration: SqsConfiguration
        session_faker: Faker
    """
    # Prepare the mocked response
    first_message = session_faker.sentence()
    second_message = session_faker.sentence()

    receipt_handle_1 = session_faker.word()
    receipt_handle_2 = session_faker.word()

    queue_url = session_faker.url()

    expected_messages = [first_message, second_message]
    mocked_response = {
        "Messages": [
            {"Body": first_message, "ReceiptHandle": receipt_handle_1},
            {"Body": second_message, "ReceiptHandle": receipt_handle_2},
        ]
    }

    with patch.object(sqs_wrapper._sqs, "receive_message") as mock_receive_message, patch.object(
        sqs_wrapper._sqs, "delete_message"
    ) as mock_delete_message, patch.object(sqs_wrapper._sqs, "get_queue_url") as mock_get_queue_url:
        mock_get_queue_url.return_value = {"QueueUrl": queue_url}
        mock_receive_message.return_value = mocked_response

        with sqs_wrapper.receive_messages() as messages:
            assert messages == expected_messages

        mock_receive_message.assert_called_once_with(
            QueueUrl=queue_url,
            MaxNumberOfMessages=sqs_wrapper_configuration.chunk_size,
            WaitTimeSeconds=sqs_wrapper_configuration.frequency,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
            VisibilityTimeout=0,
        )

        mock_delete_message.assert_any_call(QueueUrl=queue_url, ReceiptHandle=receipt_handle_1)
        mock_delete_message.assert_any_call(QueueUrl=queue_url, ReceiptHandle=receipt_handle_2)
