"""Contains AwsS3ParquetRecordsTrigger."""

import io
from collections.abc import AsyncGenerator, Sequence
from typing import Any

import orjson

from aws_helpers.parquet import iter_parquet_dataframes
from aws_helpers.utils import AsyncReader, filter_internal_traffic, seekable_file
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration
from connectors.s3.provider import AwsAccountProvider


class AwsS3FlowLogsParquetConfiguration(AwsS3QueuedConfiguration):
    """AwsS3FlowLogsTrigger configuration."""

    filter_internal_traffic: bool = True


PARQUET_BATCH_SIZE = 1_000


class BaseAwsS3FlowLogsParquetRecordsTrigger:
    """Implementation of AwsS3ParquetRecordsTrigger."""

    configuration: AwsS3FlowLogsParquetConfiguration
    name = "AWS S3 Parquet records"
    FIELD_NAMES = ("srcaddr", "dstaddr")

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        async with seekable_file(stream) as file:
            if file.seek(0, io.SEEK_END) == 0:
                return
            file.seek(0)

            # read by batches to bound memory
            for df in iter_parquet_dataframes(file, PARQUET_BATCH_SIZE):
                for record in df.to_dict(orient="records"):
                    if len(record) > 0:
                        if not filter_internal_traffic(
                            self.configuration.filter_internal_traffic,
                            (record[name] for name in self.FIELD_NAMES if name in record),
                        ):
                            yield orjson.dumps(record).decode("utf-8")
                        else:
                            DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()


class AwsS3FlowLogsParquetRecordsTrigger(
    BaseAwsS3FlowLogsParquetRecordsTrigger,
    AbstractAwsS3QueuedConnector,
    AwsAccountProvider,
):
    """AWS S3 Flow Logs Parquet Records Trigger connector."""
