"""Contains connector, configuration and module."""
import os
from asyncio import BoundedSemaphore
from typing import Any, AsyncGenerator, Generator, Optional

import orjson
from aws_helpers.utils import AsyncReader, normalize_s3_key
from connectors.metrics import INCOMING_EVENTS
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration

from crowdstrike_telemetry import CrowdStrikeTelemetryModule

from .metrics import DISCARDED_EVENTS

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


class CrowdStrikeTelemetryConnectorConfig(AwsS3QueuedConfiguration):
    # All commented fields are inherited from AwsS3QueuedConfiguration under the same names
    # chunk_size: int = 10000
    # frequency: int = 60
    # queue_name: str
    # intake_server: str | None = None
    # intake_key: str

    # this fields are also present in AwsS3QueuedConfiguration but they are not present in the json config
    # sqs_frequency: int = 10
    # delete_consumed_messages: bool = True

    queue_url: str | None = None
    is_fifo: bool | None = None


class CrowdStrikeTelemetryConnector(AbstractAwsS3QueuedConnector):
    """Implementation of CrowdStrikeTelemetryConnector."""

    name = "CrowdStrikeTelemetryConnector"
    configuration: AwsS3QueuedConfiguration
    module: CrowdStrikeTelemetryModule

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init CrowdStrikeTelemetryConnector."""
        super().__init__(*args, **kwargs)

        self.limit_of_events_to_push = int(os.getenv("AWS_BATCH_SIZE", 10000))
        self.sqs_max_messages = int(os.getenv("AWS_SQS_MAX_MESSAGES", 10))
        self.s3_max_fetch_concurrency = int(os.getenv("AWS_S3_MAX_CONCURRENCY_FETCH", 10000))
        self.s3_fetch_concurrency_sem = BoundedSemaphore(self.s3_max_fetch_concurrency)

    # Override function in order to get correct bucket and file path.
    # Schema should look like this:
    # {
    #     "cid": "uuid",
    #     "timestamp": 1662307838018,
    #     "fileCount": 1,
    #     "totalSize": 13090,
    #     "bucket": "bucket-name",
    #     "pathPrefix": "path-prefix",
    #     "files": [
    #         {
    #             "path": "path-to-file",
    #             "size": 13090,
    #             "checksum": "checksum"
    #         }
    #     ]
    # }
    def _get_object_from_notification(self, sqs_message: dict[str, Any]) -> Generator[tuple[str, str], None, None]:
        """
        Extract the file information from message
        """
        bucket = sqs_message.get("bucket")
        if bucket is None:  # pragma: no cover
            raise ValueError("Bucket is undefined", sqs_message)

        for file in sqs_message.get("files", []):
            if file is None:  # pragma: no cover
                raise ValueError("File is undefined", sqs_message)

            path = file.get("path")
            if path is None:  # pragma: no cover
                raise ValueError("File path is undefined", sqs_message)

            yield bucket, path

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
                        # This are custom CrowdStrike messages, we just parse them as it is
                        message_records.append(orjson.loads(message))
                    except ValueError as e:  # pragma: no cover
                        self.log_exception(e, message=f"Invalid JSON in message.\nInvalid message is: {message}")

                if not message_records:
                    continue_receiving = False

                INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(message_records))
                for record in message_records:
                    try:
                        # This is only one difference between this connector and the base S3 one
                        for s3_bucket, s3_key in self._get_object_from_notification(record):
                            normalized_key = normalize_s3_key(s3_key)

                            async with (
                                self.s3_fetch_concurrency_sem,
                                self.s3_wrapper.read_key(bucket=s3_bucket, key=normalized_key) as stream,
                            ):
                                async for event in self._parse_content(stream):
                                    records.append(event)

                                    if len(records) >= self.limit_of_events_to_push:
                                        continue_receiving = False
                                        result += len(await self.push_data_to_intakes(events=records))
                                        records = []

                    except Exception as e:  # pragma: no cover
                        self.log(
                            message=f"Failed to fetch content of {record}: {str(e)}",
                            level="warning",
                        )

            if not records:
                continue_receiving = False

        if records:  # pragma: no cover
            result += len(await self.push_data_to_intakes(events=records))

        return result, timestamps_to_log

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        records: AsyncGenerator[bytes, None] = (line.rstrip(b"\n") async for line in stream)

        async for record in records:
            if len(record) > 0:  # pragma: no cover
                try:
                    json_record = orjson.loads(record)
                    if (
                        json_record.get("event_simpleName") is None
                        or json_record.get("event_simpleName") in EXCLUDED_EVENT_ACTIONS
                    ):
                        DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()
                        continue

                    yield record.decode("utf-8")
                except Exception as e:
                    self.log(message=f"Failed to parse a record: {str(e)}", level="warning")
