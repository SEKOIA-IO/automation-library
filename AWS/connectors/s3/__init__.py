"""Package for all s3 connectors impl."""
from abc import ABCMeta
from functools import cached_property
from gzip import decompress

import orjson

from aws_helpers.s3_wrapper import S3Configuration, S3Wrapper
from aws_helpers.sqs_wrapper import SqsConfiguration, SqsWrapper
from aws_helpers.utils import normalize_s3_key
from connectors import AbstractAwsConnector, AbstractAwsConnectorConfiguration


class AwsS3QueuedConfiguration(AbstractAwsConnectorConfiguration):
    """Base configuration that contains SQS configuration to work with AwsS3QueuedConnector."""

    sqs_frequency: int = 10
    chunk_size: int = 10000
    delete_consumed_messages: bool = False
    queue_name: str


class AbstractAwsS3QueuedConnector(AbstractAwsConnector, metaclass=ABCMeta):
    """All connectors that use SQS to trigger S3 events."""

    configuration: AwsS3QueuedConfiguration

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

    def _parse_content(self, content: bytes) -> list[str]:  # pragma: no cover
        """
        Parse the content of the object and return a list of records.

        Args:
            content: bytes

        Returns:
             list:
        """
        raise NotImplementedError()

    @staticmethod
    def decompress_content(data: bytes) -> bytes:
        """
        Decompress content if it is compressed.

        Args:
            data:

        Returns:
            bytes:
        """
        if data[0:2] == b"\x1f\x8b":
            return decompress(data)

        return data

    async def next_batch(self) -> tuple[list[str], list[int]]:
        """
        Get next batch of messages.

        Contains main logic of the connector.

        Returns:
            list[str]:
        """
        result = []
        async with self.sqs_wrapper.receive_messages(max_messages=1) as messages:
            records = []
            timestamps_to_log: list[int] = []
            for message_data in messages:
                message, message_timestamp = message_data

                timestamps_to_log.append(message_timestamp)
                try:
                    # Records is a list of strings
                    records.extend(orjson.loads(message).get("Records", []))
                except ValueError as e:
                    self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")

            for record in records:
                try:
                    s3_bucket = record.get("s3", {}).get("bucket", {}).get("name")
                    s3_key = record.get("s3", {}).get("object", {}).get("key")

                    if s3_bucket is None:
                        raise ValueError("Bucket is undefined", record)

                    if s3_key is None:
                        raise ValueError("Key is undefined", record)

                    normalized_key = normalize_s3_key(s3_key)

                    async with self.s3_wrapper.read_key(bucket=s3_bucket, key=normalized_key) as content:
                        data = self._parse_content(self.decompress_content(content))
                        if data:
                            self.log(message=f"Forwarding {len(data)} records", level="info")

                            result.extend(await self.push_data_to_intakes(events=data))
                        else:
                            self.log(message="No records to forward", level="info")
                except Exception as e:
                    self.log(
                        message=f"Failed to fetch content of {record}: {str(e)}",
                        level="warning",
                    )

            return result, timestamps_to_log
