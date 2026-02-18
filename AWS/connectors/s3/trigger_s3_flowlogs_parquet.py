"""Contains AwsS3ParquetRecordsTrigger."""

import io
import ipaddress
from collections.abc import AsyncGenerator, Sequence
from typing import Any

import orjson
import pandas

from aws_helpers.utils import AsyncReader
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration
from connectors.s3.provider import AWSAccountProvider


class BaseAwsS3FlowLogsParquetRecordsTrigger:
    """Implementation of AwsS3ParquetRecordsTrigger."""

    configuration: AwsS3QueuedConfiguration
    name = "AWS S3 Parquet records"

    def check_all_ips_are_private(self, record: dict[str, Any], names: Sequence[str]) -> bool:
        """
        Check if all IPs in a record are private

        Args:
            input_str: str

        Returns:
            bool:
        """
        ips = []
        for name in names:
            if name in record:
                try:
                    ips.append(ipaddress.ip_address(record[name]))
                except ValueError:  # if substring is not IP then just omit it
                    pass

        return all([ip.is_private for ip in ips])

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

        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)

        for record in df.to_dict(orient="records"):
            if len(record) > 0:
                if not self.check_all_ips_are_private(record, ("srcaddr", "dstaddr")):
                    yield orjson.dumps(record).decode("utf-8")
                else:
                    DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()


class AwsS3FlowLogsParquetRecordsTrigger(
    BaseAwsS3FlowLogsParquetRecordsTrigger, AbstractAwsS3QueuedConnector, AWSAccountProvider
):
    """AWS S3 Flow Logs Parquet Records Trigger connector."""
