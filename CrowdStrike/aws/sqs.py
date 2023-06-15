"""Aws sqs client wrapper with its config class."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from async_lru import alru_cache
from loguru import logger
from pydantic import Field

from .client import AwsClient, AwsConfiguration


class SqsConfiguration(AwsConfiguration):
    """AWS SQS wrapper configuration."""

    chunk_size: int = Field(default=1, description="AWS SQS queue chunk size")
    frequency: int = Field(default=10, description="AWS SQS queue polling frequency in seconds")
    delete_consumed_messages: bool = Field(default=True, description="Delete consumed messages from queue")
    is_fifo: bool = Field(default=False, description="Is queue fifo, might ")
    queue_name: str = Field(description="AWS SQS queue name")


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
                    chunk_size = {chunk_size}
                    delete_consumed_messages = {delete_consumed_messages}
                    is_fifo = {is_fifo}
            """,
            queue_name=configuration.queue_name,
            frequency=configuration.frequency,
            chunk_size=configuration.chunk_size,
            delete_consumed_messages=configuration.delete_consumed_messages,
            is_fifo=configuration.is_fifo,
        )

    @alru_cache
    async def queue_url(self) -> str:
        """
        Get SQS queue url.

        If it is fifo then use postfix .fifo to initialize url, based on configuration.

        Returns:
            str:
        """
        queue_name = self._configuration.queue_name
        if self._configuration.is_fifo:
            queue_name = self._configuration.queue_name + ".fifo"

        async with self.get_client("sqs") as sqs:
            result = await sqs.get_queue_url(QueueName=queue_name)

            return str(result["QueueUrl"])

    @asynccontextmanager
    async def receive_messages(
        self, frequency: int | None = None, chunk_size: int | None = None, delete_consumed_messages: bool | None = None
    ) -> AsyncGenerator[list[str], None]:
        """
        Receive SQS messages.

        After processing messages they will be deleted from queue if delete_consumed_messages is True.

        Example of usage:
        with sqs.receive_messages() as messages:
            # do something with messages

        Args:
            frequency: int
            chunk_size: int
            delete_consumed_messages: int

        Yields:
            list[str]:
        """
        frequency = frequency or self._configuration.frequency
        chunk_size = chunk_size or self._configuration.chunk_size
        delete_consumed_messages = delete_consumed_messages or self._configuration.delete_consumed_messages
        queue_url = await self.queue_url()

        async with self.get_client("sqs") as sqs:
            try:
                response = await sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=chunk_size,
                    WaitTimeSeconds=frequency,
                    MessageAttributeNames=["All"],
                    AttributeNames=["All"],
                    VisibilityTimeout=0,
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
