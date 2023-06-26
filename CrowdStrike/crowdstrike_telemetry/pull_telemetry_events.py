"""Contains connector, configuration and module."""
import asyncio
from functools import cached_property
from gzip import decompress

from loguru import logger
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from aws.s3 import S3Configuration, S3Wrapper
from aws.sqs import SqsConfiguration, SqsWrapper

from . import CrowdStrikeTelemetryModule
from .schemas import CrowdStrikeNotificationSchema


class CrowdStrikeTelemetryConfig(DefaultConnectorConfiguration):
    queue_name: str
    queue_url: str | None = None
    chunk_size: int | None = None
    frequency: int | None = None
    delete_consumed_messages: bool | None = None
    is_fifo: bool | None = None


class CrowdStrikeTelemetryConnector(Connector):
    """CrowdStrikeTelemetryConnector class to work with logs."""

    name = "CrowdStrikeTelemetryConnector"
    module: CrowdStrikeTelemetryModule
    configuration: CrowdStrikeTelemetryConfig

    @cached_property
    def sqs_wrapper(self) -> SqsWrapper:
        """
        Get SQS wrapper.

        Returns:
            SqsWrapper:
        """
        config = SqsConfiguration(
            **self.module.configuration.dict(exclude_unset=True, exclude_none=True),
            **self.configuration.dict(exclude_unset=True, exclude_none=True),
        )

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

    async def get_crowdstrike_events(self) -> None:
        """
        Run CrowdStrikeTelemetry.
        """
        result: list[str] = []

        async with self.sqs_wrapper.receive_messages(delete_consumed_messages=True) as messages:
            validated_sqs_messages = []
            for message in messages:
                try:
                    validated_sqs_messages.append(CrowdStrikeNotificationSchema.parse_raw(message))
                except Exception:
                    logger.warning("Invalid notification message")

            s3_data_list = await asyncio.gather(
                *[
                    self.process_s3_file(file.path, record.bucket)
                    for record in validated_sqs_messages
                    for file in record.files
                ]
            )

            # We might have list of lists at this point we should flatten it
            for records in s3_data_list:
                result.extend(records)

        self.log(level="INFO", message=f"Found {len(result)} records to process")

        if result:
            await asyncio.to_thread(
                self.push_events_to_intakes,
                events=result,
                sync=True,
            )

    def run(self) -> None:  # pragma: no cover
        """Runs CrowdStrikeTelemetry."""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                loop.run_until_complete(self.get_crowdstrike_events())
            except Exception as e:
                self.log_exception(e, message="Error while running CrowdStrikeTelemetry")

        loop.close()

    async def process_s3_file(self, key: str, bucket: str | None = None) -> list[str]:
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
        logger.info(f"Reading file {key}")

        async with self.s3_wrapper.read_key(key, bucket) as content:
            result_content = content
            if content[0:2] == b"\x1f\x8b":
                logger.info(f"Decompressing file by key {key}")
                result_content = decompress(content)

            return [line for line in result_content.decode("utf-8").split("\n") if len(line.strip()) > 0]
