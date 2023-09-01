"""Contains connector, configuration and module."""
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import cached_property
from gzip import decompress
from typing import AsyncGenerator
from urllib.parse import urljoin

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

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

    _session: ClientSession | None = None
    _rate_limiter: AsyncLimiter | None = None

    @classmethod
    def rate_limiter(cls) -> AsyncLimiter:  # pragma: no cover
        """
        Get or initialize rate limiter.

        Returns:
            AsyncLimiter:
        """
        if cls._rate_limiter is None:
            cls._rate_limiter = AsyncLimiter(1, 1)

        return cls._rate_limiter

    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[ClientSession, None]:  # pragma: no cover
        """
        Get or initialize client session.

        Returns:
            ClientSession:
        """
        if cls._session is None:
            cls._session = ClientSession()

        async with cls.rate_limiter():
            yield cls._session

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

    async def _push_data_to_intake(self, events: list[str]) -> list[str]:  # pragma: no cover
        """
        Custom method to push events to intakes.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        self._last_events_time = datetime.utcnow()
        batch_api = urljoin(self.configuration.intake_server, "/batch")

        logger.info("Pushing total: {count} events to intakes", count=len(events))

        result_ids = []

        chunks = self._chunk_events(events, self.configuration.chunk_size)
        headers = {"User-Agent": f"sekoiaio-connector-{self.configuration.intake_key}"}
        async with self.session() as session:
            for chunk_index, chunk in enumerate(chunks):
                logger.info(
                    "Start to push chunk {chunk_index} with data count {data_count} to intakes",
                    chunk_index=chunk_index,
                    data_count=len(chunk),
                )
                request_body = {"intake_key": self.configuration.intake_key, "jsons": chunk}

                async with session.post(batch_api, headers=headers, json=request_body) as response:
                    # Not sure what response code will be at this point to identify error.
                    # Usually 200, 201, 202 ... until 300 means success
                    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status#successful_responses
                    if response.status >= 300:
                        error = await response.text()
                        logger.error(
                            "Error while pushing chunk {chunk_index} to intakes: {error}",
                            chunk_index=chunk_index,
                            error=error,
                        )

                        raise Exception(error)

                    logger.info(
                        "Successfully pushed chunk {chunk_index} to intakes",
                        chunk_index=chunk_index,
                    )
                    result = await response.json()
                    result_ids.extend(result.get("event_ids", []))

        return result_ids

    async def get_crowdstrike_events(self) -> list[str]:
        """
        Run CrowdStrikeTelemetry.

        Returns:
            list[str]:
        """
        result: list[str] = []

        async with self.sqs_wrapper.receive_messages(delete_consumed_messages=True) as messages:
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

            return await self._push_data_to_intake(result)

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

    def run(self) -> None:  # pragma: no cover
        """Runs Crowdstrike Telemetry."""
        previous_processing_end = None

        try:
            loop = asyncio.get_event_loop()

            while self.running:
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
