"""Contains AwsS3FlowLogsTrigger."""

from collections.abc import AsyncGenerator, Generator
from itertools import islice
from typing import Any, cast

from aws_helpers.utils import AsyncReader, filter_internal_traffic, is_parquet_content
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import (
    AbstractAwsS3QueuedConnector,
    AwsS3LogsBaseConfiguration,
    AwsS3QueuedConfiguration,
)
from connectors.s3.provider import AwsAccountProvider


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

    def _read_content(self, content: bytes) -> Generator[str, None, None]:
        """
        Read the content of the S3 Object

        Args:
            content: bytes

        Returns:
            Generator[str, None, None]: The content as a generator of strings
        """
        for record in content.decode("utf-8").split(self.configuration.sep):
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
        content = await stream.read()

        if is_parquet_content(content):
            self._warn_parquet_content()
            return

        records: Generator[str, None, None] = self._read_content(content)
        if self.configuration.ignore_comments:  # pragma: no cover
            records = (record for record in records if not record.strip().startswith("#"))

        for record in islice(records, self.configuration.skip_first, None):
            yield record


class AwsS3FlowLogsTrigger(BaseAwsS3FlowLogsTrigger, AbstractAwsS3QueuedConnector, AwsAccountProvider):
    """AWS S3 Flow Logs Trigger connector."""
