"""Contains connector, configuration and module."""
import asyncio
import hashlib
import os
import time
from functools import cached_property
from gzip import decompress
from typing import Tuple

from loguru import logger
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from aws.s3 import S3Configuration, S3Wrapper
from aws.sqs import SqsConfiguration, SqsWrapper

from . import CrowdStrikeTelemetryModule
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS
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

    async def _push_events(self, events: list[str]) -> list[str]:
        """
        Push events to intakes.

        Simple wrapper over `self.push_events_to_intakes` to run it async.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        logger.info("Pushing {count} events to intakes", count=len(events))

        return await asyncio.to_thread(
            self.push_events_to_intakes,
            events=events,
            sync=True,
        )

    async def get_crowdstrike_events(self) -> list[str]:
        """
        Run CrowdStrikeTelemetry.
        """
        result: list[str] = []
        files_to_delete: list[PersistentJSON] = []

        async with self.sqs_wrapper.receive_messages(delete_consumed_messages=True) as messages:
            validated_sqs_messages = []
            for message in messages:
                try:
                    validated_sqs_messages.append(CrowdStrikeNotificationSchema.parse_raw(message))
                except Exception:
                    logger.warning("Invalid notification message")

            pushed_events_data = await asyncio.gather(
                *[
                    self.process_s3_file_and_push_to_intake(file.path, record.bucket)
                    for record in validated_sqs_messages
                    for file in record.files
                ]
            )

            for records in pushed_events_data:
                result.extend(records[0])
                files_to_delete.append(records[1])

        for persistent_file in files_to_delete:
            os.remove(persistent_file._filepath)

        return result

    async def process_s3_file_and_push_to_intake(
        self, key: str, bucket: str | None = None
    ) -> Tuple[list[str], PersistentJSON]:
        """
        Process S3 object and push data to intake.

        If it is a compressed file, it will be decompressed, otherwise it will be read as json.

        Args:
            key: str
            bucket: str | None

        Returns:
            Tuple[list[str], PersistentJSON]: list of event ids and path to lock file

        Raises:
            Exception: Unexpected result type
        """
        lock_key = key + (bucket or "")
        local_file_lock_key = "{0}.json".format(hashlib.md5(lock_key.encode()).hexdigest())
        local_file_lock = PersistentJSON(local_file_lock_key)

        with local_file_lock as cached_data:
            if "events_count" in cached_data:
                logger.info(f"File {key} already processed")

                return [], local_file_lock

        result = await self.process_s3_file(key, bucket)

        log_message = f"Found {len(result)} records to process"
        self.log(level="INFO", message=f"Found {len(result)} records to process")
        logger.info(log_message)
        push_result = await self._push_events(result)

        with local_file_lock as cached_data:
            cached_data["events_count"] = len(push_result)

        return push_result, local_file_lock

    async def process_s3_file(self, key: str, bucket: str | None = None) -> list[str]:
        """
        Process S3 objects.

        If it is a compressed file, it will be decompressed, otherwise it will be read as json.

        Args:
            key: str
            bucket: str | None

        Returns:
            list[str]: list of events inside file

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

    def run(self) -> None:  # pragma: no cover
        """Runs Crowdstrike Telemetry."""
        loop = asyncio.get_event_loop()

        previous_processing_end = None
        try:
            while True:
                processing_start = time.time()
                if previous_processing_end is not None:
                    EVENTS_LAG.labels(intake_key=self.configuration.intake_key).observe(
                        processing_start - previous_processing_end
                    )

                message_ids: list[str] = loop.run_until_complete(self.get_crowdstrike_events())
                processing_end = time.time()
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_ids))

                log_message = "No records to forward"
                if len(message_ids) > 0:
                    log_message = "Pushed {0} records".format(len(message_ids))

                logger.info(log_message)
                self.log(message=log_message, level="info")

                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                    processing_end - processing_start
                )

                previous_processing_end = processing_end

        except Exception as e:
            logger.error("Error while running CrowdStrike Telemetry: {error}", error=e)

        finally:
            loop.close()
