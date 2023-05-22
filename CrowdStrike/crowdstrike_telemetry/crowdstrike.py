"""Contains connector, configuration and module."""
import asyncio
from functools import cached_property
from gzip import decompress
from typing import Any, Dict, List

import orjson
from loguru import logger
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.module import Module

from aws.s3 import S3Configuration, S3Wrapper
from aws.sqs import SqsConfiguration, SqsWrapper

from .schemas import CrowdStrikeNotificationSchema


class CrowdStrikeTelemetryConfig(DefaultConnectorConfiguration):
    """Configuration for CrowdStrikeTelemetryConnector."""

    aws_secret_access_key: str
    aws_access_key_id: str
    queue_name: str
    aws_region: str

    chunk_size: int | None = None
    frequency: int | None = None
    delete_consumed_messages: bool | None = None
    is_fifo: bool | None = None


class CrowdStrikeTelemetryModule(Module):
    """CrowdStrikeTelemetryModule."""

    configuration: CrowdStrikeTelemetryConfig


class CrowdStrikeTelemetryConnector(Connector):
    """CrowdStrikeTelemetryConnector class to work with logs."""

    name = "CrowdStrikeTelemetryConnector"
    module: CrowdStrikeTelemetryModule

    @cached_property
    def sqs_wrapper(self) -> SqsWrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        config = SqsConfiguration(**self.module.configuration.dict(exclude_unset=True, exclude_none=True))

        return SqsWrapper(config)

    @cached_property
    def s3_wrapper(self) -> S3Wrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        config = S3Configuration(**self.module.configuration.dict(exclude_unset=True, exclude_none=True))

        return S3Wrapper(config)

    async def get_crowdstrike_events(self) -> List[Dict[Any, Any]]:
        """
        Run CrowdStrikeTelemetry.

        Returns:
            list[dict]:
        """
        async with self.sqs_wrapper.receive_messages(delete_consumed_messages=True) as messages:
            validated_sqs_messages = [CrowdStrikeNotificationSchema.parse_raw(content) for content in messages]

            s3_data_list = await asyncio.gather(
                *[
                    self.process_s3_file(file.path, record.bucket)
                    for record in validated_sqs_messages
                    for file in record.files
                ]
            )

            # We might have list of lists at this point we should flatten it
            result = []
            for record in s3_data_list:
                if isinstance(record, list):
                    for item in record:
                        result.append(item)
                else:
                    result.append(record)

        logger.info("Found {0} records to process".format(len(result)))

        self.push_events_to_intakes(events=result)

        return result

    def run(self) -> None:
        """Runs CrowdStrikeTelemetry."""
        loop = asyncio.get_event_loop()

        while True:
            loop.run_until_complete(self.get_crowdstrike_events())

    async def process_s3_file(self, key: str, bucket: str | None = None) -> List[Dict[Any, Any]]:
        """
        Process S3 objects.

        If it is a compressed file, it will be decompressed, otherwise it will be read as json.

        Args:
            key: str
            bucket: str | None

        Returns:
            list[dict]:

        Raises:
            Exception: Unexpected result type
        """
        logger.info("Reading file {0}".format(key))

        async with self.s3_wrapper.read_key(key, bucket) as content:
            result_content = content
            if content[0:2] == b"\x1f\x8b":
                logger.info("Decompressing file by key {0}".format(key))
                result_content = decompress(content)

            result_str = result_content.decode("utf-8")

            result = orjson.loads(result_str)

            # Mypy fails if using isinstance inside pattern matching
            if isinstance(result, list):
                return result

            elif isinstance(result, dict):
                return [result]

            raise Exception("Unexpected result type. Expected list of objects or object, got \n {0}".format(result))
