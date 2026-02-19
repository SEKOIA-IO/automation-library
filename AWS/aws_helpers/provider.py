import asyncio
from abc import ABCMeta, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from aws_helpers.utils import AsyncReader


class AwsS3Client(Protocol):
    @abstractmethod
    def read_key(
        self, key: str, bucket: str | None = None, loop: asyncio.AbstractEventLoop | None = None
    ) -> AbstractAsyncContextManager[AsyncReader]:
        """
        Reads content from S3 object.

        Args:
            key: str
            bucket: str | None: if not provided, then use default bucket from configuration

        Yields:
            AsyncReader: The reader of the S3 object
        """
        raise NotImplementedError()


class AwsSqsClient(Protocol):
    @abstractmethod
    def receive_messages(
        self,
        frequency: int | None = None,
        max_messages: int = 10,
        delete_consumed_messages: bool | None = None,
        visibility_timeout: int | None = None,
    ) -> AbstractAsyncContextManager[list[tuple[str, int]]]:
        """
        Receive SQS messages.

        After processing messages they will be deleted from queue if delete_consumed_messages is True.

        Example of usage:
        async def process_messages(sqs: AwsSqsClient) -> None:
            async with sqs.receive_messages() as messages:
                # do something with messages
                ...

        Args:
            frequency: int
            max_messages: int
            delete_consumed_messages: int
            visibility_timeout: int

        Yields:
            list[tuple[str, int]]: list of message content and message sent timestamp
        """
        raise NotImplementedError()


class AwsProvider(metaclass=ABCMeta):
    """
    AWS provider
    """

    @property
    def s3_wrapper(self) -> AwsS3Client:
        """
        Get S3 client

        Returns:
            AwsS3Client: The S3 client
        """
        raise NotImplementedError()

    @property
    def sqs_wrapper(self) -> AwsSqsClient:
        """
        Get SQS client.

        Returns:
            AwsSqsClient: The SQS client
        """
        raise NotImplementedError()
