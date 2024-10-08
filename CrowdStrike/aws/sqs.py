"""Aws sqs client wrapper with its config class."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from async_lru import alru_cache
from loguru import logger
from pydantic import Field

from .client import AwsClient, AwsConfiguration


class SqsConfiguration(AwsConfiguration):
    """AWS SQS wrapper configuration."""

    frequency: int = Field(default=10, description="AWS SQS queue polling frequency in seconds")
    delete_consumed_messages: bool = Field(default=True, description="Delete consumed messages from queue")
    is_fifo: bool = Field(default=False, description="Is queue fifo, might ")
    queue_name: str = Field(description="AWS SQS queue name")
    queue_url: str | None = Field(descripton="AWS SQS queue url")


class SqsWrapper(AwsClient[SqsConfiguration]):
    """Aws SQS wrapper."""

    def __init__(self, configuration: SqsConfiguration) -> None:
        """
        Initialize SqsTest.

        Args:
            configuration: AWS configuration
        """
        super().__init__(configuration)

        logger.info(
            """
                Initializing SQS client with configuration:
                    queue_name = {queue_name}
                    frequency = {frequency}
                    delete_consumed_messages = {delete_consumed_messages}
                    is_fifo = {is_fifo}
                    queue_url = {queue_url}
            """,
            queue_name=configuration.queue_name,
            frequency=configuration.frequency,
            delete_consumed_messages=configuration.delete_consumed_messages,
            is_fifo=configuration.is_fifo,
            queue_url=configuration.queue_url,
        )

    @alru_cache
    async def queue_url(self) -> str:
        """
        Get SQS queue url.

        If defined, returns the value in the configuration
        If it is fifo then use postfix .fifo to initialize url, based on configuration.

        Returns:
            str:
        """

        queue_url = self._configuration.queue_url
        if queue_url:
            return queue_url

        queue_name = self._configuration.queue_name
        if self._configuration.is_fifo:
            queue_name = self._configuration.queue_name + ".fifo"

        async with self.get_client("sqs") as sqs:
            result = await sqs.get_queue_url(QueueName=queue_name)

            return str(result["QueueUrl"])

    @asynccontextmanager
    async def receive_messages(
        self, frequency: int | None = None, max_messages: int = 10, delete_consumed_messages: bool | None = None
    ) -> AsyncGenerator[list[str], None]:
        """
        Receive SQS messages.

        After processing messages they will be deleted from queue if delete_consumed_messages is True.

        Example of usage:
        with sqs.receive_messages() as messages:
            # do something with messages

        Args:
            frequency: int
            max_messages: int
            delete_consumed_messages: int

        Yields:
            list[str]:
        """
        if max_messages < 1 or max_messages > 10:
            raise ValueError("max_messages should be between 1 and 10")

        frequency = frequency or self._configuration.frequency
        delete_consumed_messages = delete_consumed_messages or self._configuration.delete_consumed_messages
        queue_url = await self.queue_url()

        async with self.get_client("sqs") as sqs:
            try:
                response = await sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=max_messages,
                    WaitTimeSeconds=frequency,
                    MessageAttributeNames=["All"],
                    AttributeNames=["All"],
                    VisibilityTimeout=60,
                )

            except Exception as e:
                logger.error(f"Failed to receive messages from sqs: {e}")

                raise e

            result = []

            try:
                for message in response.get("Messages", []):
                    result.append(message["Body"])

                logger.info(f"Received {len(result)} messages from sqs queue {self._configuration.queue_name}")

                yield result
            finally:
                # We should delete messages from queue after releasing context manager if it is configured
                if delete_consumed_messages and response.get("Messages", []):
                    logger.info("Deleting consumed messages from sqs")
                    for message in response.get("Messages", []):
                        await sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
