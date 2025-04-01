"""Package for all s3 connectors impl."""

import os
from abc import ABCMeta
from collections.abc import AsyncGenerator
from functools import cached_property
from typing import Any, BinaryIO, Optional

import orjson

from aws_helpers.s3_wrapper import S3Configuration, S3Wrapper
from aws_helpers.sqs_wrapper import SqsConfiguration, SqsWrapper
from aws_helpers.utils import normalize_s3_key, AsyncReader
from connectors import AbstractAwsConnector, AbstractAwsConnectorConfiguration
from connectors.metrics import INCOMING_EVENTS


class AwsS3QueuedConfiguration(AbstractAwsConnectorConfiguration):
    """Base configuration that contains SQS configuration to work with AwsS3QueuedConnector."""

    sqs_frequency: int = 10
    chunk_size: int = 10000
    delete_consumed_messages: bool = True
    queue_name: str


class AbstractAwsS3QueuedConnector(AbstractAwsConnector, metaclass=ABCMeta):
    """All connectors that use SQS to trigger S3 events."""

    configuration: AwsS3QueuedConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init AbstractAwsS3QueuedConnector."""

        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("AWS_BATCH_SIZE", 10000))
        self.sqs_max_messages = int(os.getenv("AWS_SQS_MAX_MESSAGES", 10))

    @cached_property
    def s3_wrapper(self) -> S3Wrapper:
        """
        Get S3 wrapper.

        Returns:
            S3Wrapper:
        """
        config = S3Configuration(
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )

        return S3Wrapper(config)

    @cached_property
    def sqs_wrapper(self) -> SqsWrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        config = SqsConfiguration(
            frequency=self.configuration.sqs_frequency,
            delete_consumed_messages=self.configuration.delete_consumed_messages,
            queue_name=self.configuration.queue_name,
            aws_access_key_id=self.module.configuration.aws_access_key,
            aws_secret_access_key=self.module.configuration.aws_secret_access_key,
            aws_region=self.module.configuration.aws_region_name,
        )

        return SqsWrapper(config)

    def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:  # pragma: no cover
        """
        Parse the content of the S3 object and return the records as a generator.

        Args:
            stream: BinaryIO

        Returns:
             Generator:
        """
        raise NotImplementedError()

    def _get_notifs_from_sqs_message(self, sqs_message: str) -> list[dict[str, Any]]:
        """
        Extract the records from the SQS message
        """
        return orjson.loads(sqs_message).get("Records") or []

    def _get_object_from_notification(self, notification: dict[str, Any]) -> tuple[str | None, str | None]:
        """
        Extract the object information from notificiation
        """
        return notification.get("s3", {}).get("bucket", {}).get("name"), notification.get("s3", {}).get(
            "object", {}
        ).get("key")

    async def next_batch(self, previous_processing_end: float | None = None) -> tuple[int, list[int]]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Args:
            previous_processing_end: float | None

        Returns:
            tuple[int, list[int]]:
        """
        records = []
        result = 0
        timestamps_to_log: list[int] = []

        continue_receiving = True

        while continue_receiving:
            async with self.sqs_wrapper.receive_messages(max_messages=self.sqs_max_messages) as messages:
                message_records = []

                if not messages:
                    continue_receiving = False

                for message_data in messages:
                    message, message_timestamp = message_data

                    timestamps_to_log.append(message_timestamp)
                    try:
                        # Records is a list of strings
                        message_records.extend(self._get_notifs_from_sqs_message(message))
                    except ValueError as e:
                        self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")

                INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_records))
                for record in message_records:
                    try:
                        s3_bucket, s3_key = self._get_object_from_notification(record)

                        if s3_bucket is None:
                            raise ValueError("Bucket is undefined", record)

                        if s3_key is None:
                            raise ValueError("Key is undefined", record)

                        normalized_key = normalize_s3_key(s3_key)

                        async with self.s3_wrapper.read_key(bucket=s3_bucket, key=normalized_key) as stream:
                            async for event in self._parse_content(stream):
                                records.append(event)

                                if len(records) >= self.limit_of_events_to_push:
                                    continue_receiving = False
                                    result += len(await self.push_data_to_intakes(events=records))
                                    records = []

                    except Exception as e:
                        self.log(
                            message=f"Failed to fetch content of {record}: {str(e)}",
                            level="warning",
                        )

            if not records:
                continue_receiving = False

        if records:
            result += len(await self.push_data_to_intakes(events=records))

        return result, timestamps_to_log
