"""Contains AwsS3ParquetRecordsTrigger."""

import io
from collections.abc import AsyncGenerator
from typing import Any

import orjson

from aws_helpers.parquet import iter_parquet_dataframes
from aws_helpers.utils import AsyncReader, seekable_file
from connectors.s3 import AbstractAwsS3QueuedConnector
from connectors.s3.provider import AwsAccountProvider

PARQUET_BATCH_SIZE = 10_000


class BaseAwsS3OcsfTrigger:
    """Implementation of AwsS3OcsfTrigger."""

    name = "AWS S3 OCSF records"

    def _get_notifs_from_sqs_message(self, sqs_message: str) -> list[dict[str, Any]]:
        """
        Extract the records from the SQS message
        """
        return [orjson.loads(sqs_message)]

    def _get_object_from_notification(self, notification: dict[str, Any]) -> tuple[str | None, str | None]:
        """
        Extract the object information from notificiation
        """
        return notification.get("detail", {}).get("bucket", {}).get("name"), notification.get("detail", {}).get(
            "object", {}
        ).get("key")

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
                for record in orjson.loads(df.to_json(orient="records")):
                    if len(record) > 0:
                        yield orjson.dumps(record).decode("utf-8")


class AwsS3OcsfTrigger(BaseAwsS3OcsfTrigger, AbstractAwsS3QueuedConnector, AwsAccountProvider):
    """AWS S3 OCSF Trigger connector."""
