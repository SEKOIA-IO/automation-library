"""Contains AwsS3ParquetRecordsTrigger."""

import io
from collections.abc import AsyncGenerator
from typing import Any

import orjson
import pandas

from aws_helpers.utils import AsyncReader
from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3OcsfTrigger(AbstractAwsS3QueuedConnector):
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
        content = await stream.read()

        if len(content) == 0:
            return

        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)
        records = orjson.loads(df.to_json(orient="records"))

        for record in records:
            if len(record) > 0:
                yield orjson.dumps(record).decode("utf-8")
