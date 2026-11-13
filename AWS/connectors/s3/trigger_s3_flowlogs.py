"""Contains AwsS3FlowLogsTrigger."""

from collections.abc import AsyncGenerator
from typing import Any, cast

from aws_helpers.utils import (
    PARQUET_MAGIC,
    AsyncReader,
    PeekableStreamReader,
    async_islice,
    filter_internal_traffic,
    has_parquet_footer,
    split_stream_by_separator,
)
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import (
    AbstractAwsS3QueuedConnector,
    AwsS3LogsBaseConfiguration,
    AwsS3QueuedConfiguration,
)
from connectors.s3.provider import AwsAccountProvider

# reads go through a thread pool: bigger chunks than the helper default avoid one round-trip per KB
READ_CHUNK_SIZE = 64 * 1024


class AwsS3FlowLogsConfiguration(AwsS3QueuedConfiguration, AwsS3LogsBaseConfiguration):
    """AwsS3FlowLogsTrigger configuration."""

    ignore_comments: bool = False
    filter_internal_traffic: bool = True


class BaseAwsS3FlowLogsTrigger:
    """Implementation of AwsS3FlowLogsTrigger."""

    configuration: AwsS3FlowLogsConfiguration
    name = "AWS S3 Flow Logs"

    def _warn_parquet_content(self) -> None:
        """Log a warning when Parquet content is sent to the text flow logs trigger."""
        cast(Any, self).log(
            message=(
                "Parquet content detected in AWS S3 Flow Logs text trigger. "
                "Use the AWS S3 Parquet records trigger (Fetch new FlowLogs Parquet records on S3) "
                "for .parquet objects."
            ),
            level="warning",
        )

    async def _read_content(self, stream: PeekableStreamReader) -> AsyncGenerator[str, None]:
        """
        Read the content of the S3 Object, record by record

        Args:
            stream: PeekableStreamReader

        Returns:
            AsyncGenerator[str, None]: The content as a generator of strings
        """
        separator = self.configuration.sep.encode("utf-8")
        async for chunk in split_stream_by_separator(stream, separator, chunk_size=READ_CHUNK_SIZE):
            record = chunk.decode("utf-8")
            if len(record) > 0:
                if not filter_internal_traffic(self.configuration.filter_internal_traffic, record.split(" ")):
                    yield record
                else:
                    DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             AsyncGenerator[str, None]:
        """
        reader = PeekableStreamReader(stream)

        # a complete Parquet file starts and ends with the magic bytes: anything else is parsed as text
        if await reader.peek(len(PARQUET_MAGIC)) == PARQUET_MAGIC and await has_parquet_footer(stream):
            self._warn_parquet_content()
            return

        records = self._read_content(reader)
        if self.configuration.ignore_comments:  # pragma: no cover
            records = (record async for record in records if not record.strip().startswith("#"))

        async for record in async_islice(records, self.configuration.skip_first, None):
            yield record


class AwsS3FlowLogsTrigger(BaseAwsS3FlowLogsTrigger, AbstractAwsS3QueuedConnector, AwsAccountProvider):
    """AWS S3 Flow Logs Trigger connector."""
