"""Package for all s3 connectors impl."""

import os
from abc import ABCMeta
from asyncio import BoundedSemaphore
from collections.abc import AsyncGenerator
from typing import Any, Optional

import orjson
from pydantic import BaseModel, Field
from sekoia_automation.storage import PersistentJSON

from aws_helpers.utils import AsyncReader, normalize_s3_key, unescape_string
from connectors import AbstractAwsConnector, AbstractAwsConnectorConfiguration
from connectors.metrics import INCOMING_EVENTS


class AwsS3QueuedConfiguration(AbstractAwsConnectorConfiguration):
    """Base configuration that contains SQS configuration to work with AwsS3QueuedConnector."""

    sqs_frequency: int = 10
    chunk_size: int = 10000
    delete_consumed_messages: bool = True
    queue_name: str
    prefix_filter: str | None = None


class AwsS3ListConfiguration(AbstractAwsConnectorConfiguration):
    """Base configuration to work with AbstractAwsS3ListConnector (without SQS)."""

    bucket: str
    prefix_filter: str | None = None


class AwsS3LogsBaseConfiguration(BaseModel):
    skip_first: int = 0
    separator: str = Field(min_length=1)

    @property
    def sep(self) -> str:
        # actual separator
        return unescape_string(self.separator)


class AbstractAwsS3QueuedConnector(AbstractAwsConnector, metaclass=ABCMeta):
    """All connectors that use SQS to trigger S3 events."""

    configuration: AwsS3QueuedConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        """Init AbstractAwsS3QueuedConnector."""

        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("AWS_BATCH_SIZE", 10000))
        self.sqs_max_messages = int(os.getenv("AWS_SQS_MAX_MESSAGES", 10))
        self.sqs_visibility_timeout = int(os.getenv("AWS_SQS_VISIBILITY_TIMEOUT", 60))
        self.s3_max_fetch_concurrency = int(os.getenv("AWS_S3_MAX_CONCURRENCY_FETCH", 10000))
        self.s3_fetch_concurrency_sem = BoundedSemaphore(self.s3_max_fetch_concurrency)

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
            messages: list[tuple[str, int]]
            async with self.sqs_wrapper.receive_messages(
                max_messages=self.sqs_max_messages,
                visibility_timeout=self.sqs_visibility_timeout,
            ) as messages:
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
                        self.log_exception(
                            e,
                            message=f"Invalid JSON in message.\nInvalid message is: {message}",
                        )

                if not message_records:
                    continue_receiving = False

                INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key, **self.scalability_labels).inc(
                    len(message_records)
                )
                for record in message_records:
                    try:
                        s3_bucket, s3_key = self._get_object_from_notification(record)

                        if s3_bucket is None:
                            raise ValueError("Bucket is undefined", record)

                        if s3_key is None:
                            raise ValueError("Key is undefined", record)

                        normalized_key = normalize_s3_key(s3_key)

                        if self.configuration.prefix_filter and not normalized_key.startswith(
                            self.configuration.prefix_filter
                        ):
                            self.log(
                                message=f"Skipping S3 object {normalized_key}: does not match prefix filter "
                                f"'{self.configuration.prefix_filter}'",
                                level="debug",
                            )
                            continue

                        stream: AsyncReader
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


class AbstractAwsS3ListConnector(AbstractAwsConnector, metaclass=ABCMeta):
    """
    Connector that collects objects from a S3 bucket without relying on SQS notifications.

    It lists the objects present in the bucket, reads every new object and uses a checkpoint
    (the key of the last processed object) to avoid reading the same file multiple times.
    """

    configuration: AwsS3ListConfiguration

    def __init__(self, *args: Any, **kwargs: Optional[Any]) -> None:
        super().__init__(*args, **kwargs)
        self.limit_of_events_to_push = int(os.getenv("AWS_BATCH_SIZE", 10000))
        self.s3_max_fetch_concurrency = int(os.getenv("AWS_S3_MAX_CONCURRENCY_FETCH", 10000))
        self.s3_fetch_concurrency_sem = BoundedSemaphore(self.s3_max_fetch_concurrency)
        self.context = PersistentJSON("context.json", self.data_path)

    def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:  # pragma: no cover
        raise NotImplementedError()

    def read_marker(self) -> str | None:
        """Get the marker (key of the last processed object) from the previous run."""
        with self.context as cache:
            marker = cache.get("marker")
            return marker if isinstance(marker, str) else None

    def write_marker(self, marker: str) -> None:
        """Persist the marker (key of the last processed object)."""
        with self.context as cache:
            cache["marker"] = marker

    async def next_batch(self) -> tuple[int, list[int]]:
        """List objects after the checkpoint, read each one and advance the marker."""
        records: list[str] = []
        result = 0
        timestamps_to_log: list[int] = []

        marker = self.read_marker()
        last_committed = marker
        last_processed = marker

        async for s3_object in self.s3_wrapper.list_objects(
            bucket=self.configuration.bucket,
            prefix=self.configuration.prefix_filter,
            start_after=marker,
        ):
            key = s3_object.get("Key")
            if not key:
                continue

            normalized_key = normalize_s3_key(key)
            last_modified = s3_object.get("LastModified")
            if last_modified is not None:
                timestamps_to_log.append(int(last_modified.timestamp() * 1000))

            try:
                stream: AsyncReader
                async with (
                    self.s3_fetch_concurrency_sem,
                    self.s3_wrapper.read_key(bucket=self.configuration.bucket, key=normalized_key) as stream,
                ):
                    object_records = [event async for event in self._parse_content(stream)]

            except Exception as e:
                # do not advance the marker past a failing object to avoid losing data.
                self.log(message=f"Failed to fetch content of {key}: {str(e)}", level="warning")
                break

            last_processed = key

            INCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(object_records))
            records.extend(object_records)

            if len(records) >= self.limit_of_events_to_push:
                result += len(await self.push_data_to_intakes(events=records))
                records = []
                if last_processed is not None and last_processed != last_committed:
                    self.write_marker(last_processed)
                    last_committed = last_processed

        if records:
            result += len(await self.push_data_to_intakes(events=records))

        if last_processed is not None and last_processed != last_committed:
            self.write_marker(last_processed)

        return result, timestamps_to_log
