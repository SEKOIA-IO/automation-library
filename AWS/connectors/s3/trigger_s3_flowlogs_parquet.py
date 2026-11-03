"""Contains AwsS3ParquetRecordsTrigger."""

import io
from collections.abc import AsyncGenerator, Sequence
from typing import Any

import orjson
import pandas
import pyarrow.parquet

from aws_helpers.utils import AsyncReader, filter_internal_traffic
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import (
    AbstractAwsS3QueuedConnector,
    AwsS3LogsBaseConfiguration,
    AwsS3QueuedConfiguration,
)
from connectors.s3.provider import AwsAccountProvider


class AwsS3FlowLogsParquetConfiguration(AwsS3QueuedConfiguration, AwsS3LogsBaseConfiguration):
    """AwsS3FlowLogsTrigger configuration."""

    filter_internal_traffic: bool = True


def _nullable_integer_columns(parquet: pyarrow.parquet.ParquetFile) -> set[str]:
    """Find file-wide integer nullability, even when Parquet statistics are absent."""
    integer_columns = {field.name for field in parquet.schema_arrow if pyarrow.types.is_integer(field.type)}
    nullable: set[str] = set()
    unknown: set[str] = set()
    for row_group_index in range(parquet.num_row_groups):
        row_group = parquet.metadata.row_group(row_group_index)
        for column_index in range(row_group.num_columns):
            column = row_group.column(column_index)
            if column.path_in_schema not in integer_columns:
                continue
            statistics = column.statistics
            if statistics is None or statistics.null_count is None:
                unknown.add(column.path_in_schema)
            elif statistics.null_count > 0:
                nullable.add(column.path_in_schema)

    # Missing statistics must not silently turn a nullable integer into an integer
    # in early batches. Scan only unresolved columns, without retaining their rows.
    unresolved = unknown - nullable
    if unresolved:
        for batch in parquet.iter_batches(batch_size=1000, columns=sorted(unresolved)):
            nullable.update(name for name in unresolved if batch.column(name).null_count > 0)
            if unresolved <= nullable:
                break
    return nullable


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
        content = await stream.read()
        if len(content) == 0:
            return

        # Keep pandas' record conversion semantics without materializing the entire
        # decompressed file and its Python dictionaries at the same time.
        with io.BytesIO(content) as reader, pyarrow.parquet.ParquetFile(reader) as parquet:
            nullable_integer_columns = _nullable_integer_columns(parquet)
            for batch in parquet.iter_batches(batch_size=1000):
                frame = batch.to_pandas()
                for name in nullable_integer_columns:
                    if name not in frame.columns:
                        continue
                    dtype = frame[name].dtype
                    # Preserve explicit pandas extension dtypes (e.g. Int64), but
                    # match full-file pandas conversion for NumPy integer columns.
                    if dtype.kind in "iu" and not isinstance(dtype, pandas.api.extensions.ExtensionDtype):
                        frame[name] = frame[name].astype("float64")
                for record in frame.to_dict(orient="records"):
                    if len(record) > 0:
                        if not filter_internal_traffic(
                            self.configuration.filter_internal_traffic,
                            (record[name] for name in self.FIELD_NAMES if name in record),
                        ):
                            yield orjson.dumps(record).decode("utf-8")
                        else:
                            DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()


class AwsS3FlowLogsParquetRecordsTrigger(
    BaseAwsS3FlowLogsParquetRecordsTrigger, AbstractAwsS3QueuedConnector, AwsAccountProvider
):
    """AWS S3 Flow Logs Parquet Records Trigger connector."""
