"""Contains connector, configuration and module."""

import json
import asyncio
import time
from functools import cached_property
from gzip import decompress

from loguru import logger
from sekoia_automation.aio.connector import AsyncConnector
from sekoia_automation.connector import DefaultConnectorConfiguration

from aws.s3 import S3Configuration, S3Wrapper
from aws.sqs import SqsConfiguration, SqsWrapper

from . import CrowdStrikeTelemetryModule
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, OUTCOMING_EVENTS, DISCARDED_EVENTS
from .schemas import CrowdStrikeNotificationSchema

EXCLUDED_EVENT_ACTIONS = [
    "SensorHeartbeat",
    "ConfigStateUpdate",
    "ErrorEvent",
    "FalconServiceStatus",
    "CurrentSystemTags",
    "BillingInfo",
    "ChannelActive",
    "IdpDcPerfReport",
    "ProvisioningChannelVersionRequired",
    "ChannelVersionRequired",
    "SensorSelfDiagnosticTelemetry",
    "SystemCapacity",
    "MobilePowerStats",
    "DeliverRulesEngineResultsToCloud",
    "NeighborListIP4",
    "NeighborListIP6",
    "AgentConnect",
    "AgentOnline",
    "ResourceUtilization",
]


class CrowdStrikeTelemetryConfig(DefaultConnectorConfiguration):
    queue_name: str
    queue_url: str | None = None
    chunk_size: int | None = None
    frequency: int | None = None
    delete_consumed_messages: bool | None = None
    is_fifo: bool | None = None


class CrowdStrikeTelemetryConnector(AsyncConnector):
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

    async def get_crowdstrike_events(self) -> list[str]:
        """
        Run CrowdStrikeTelemetry.

        Returns:
            list[str]:
        """
        result: list[str] = []

        async with self.sqs_wrapper.receive_messages(delete_consumed_messages=True, max_messages=10) as messages:
            validated_sqs_messages = []
            for message in messages:
                try:
                    validated_sqs_messages.append(CrowdStrikeNotificationSchema.parse_raw(message))
                except Exception:  # pragma: no cover
                    logger.warning("Invalid notification message {invalid_message}", invalid_message=message)

            if validated_sqs_messages:  # pragma: no cover
                logger.info("Found {sqs_messages} entries in sqs", sqs_messages=len(validated_sqs_messages))

                s3_data_list = await asyncio.gather(
                    *[
                        self.process_s3_file(file.path, record.bucket)
                        for record in validated_sqs_messages
                        for file in record.files
                    ]
                )

                # We have list of lists her, so we should flatten it
                for records in s3_data_list:
                    result.extend(records)
            else:  # pragma: no cover
                logger.info("No messages in sqs")

            self.log(level="INFO", message=f"Found {len(result)} records to process")

            pushed_ids: list[str] = await self.push_data_to_intakes(result)

            return pushed_ids

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
        result = []
        for line in result_content.decode("utf-8").split("\n"):
            if len(line.strip()) > 0:
                try:
                    event = json.loads(line)
                    if (
                        event.get("event_simpleName") is None
                        or event.get("event_simpleName") in EXCLUDED_EVENT_ACTIONS
                    ):
                        DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
                        continue
                    result.append(line)
                except Exception as any_exception:
                    logger.error(
                        "failed to read line from event stream",
                        line=line,
                        stream_root_url=self.stream_root_url,
                    )
                    self.log_exception(any_exception)
        return result

    def run(self) -> None:  # pragma: no cover
        """Runs Crowdstrike Telemetry."""
        previous_processing_end = None

        while self.running:
            try:
                loop = asyncio.get_event_loop()

                while self.running:
                    processing_start = time.time()
                    if previous_processing_end is not None:
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(
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
                    logger.info(log_message)
                    logger.info(
                        "Processing took {processing_time} seconds",
                        processing_time=(processing_end - processing_start),
                    )

                    FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(
                        processing_end - processing_start
                    )

                    previous_processing_end = processing_end

            except Exception as e:
                logger.error("Error while running CrowdStrike Telemetry: {error}", error=e)
