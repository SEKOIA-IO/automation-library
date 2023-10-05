"""Contains AwsS3ParquetRecordsTrigger."""
import io

import orjson
import pandas

from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3ParquetRecordsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3ParquetRecordsTrigger."""

    name = "AWS S3 Parquet records"

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse the content of the object and return a list of records.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        if len(content) == 0:
            return []

        # TODO: Check if we should save file locally with aiofiles and read it with pandas
        reader = io.BytesIO(content)
        df = pandas.read_parquet(reader)

        records = []
        for record in df.to_dict(orient="records"):
            if len(record) > 0:
                records.append(orjson.dumps(record).decode("utf-8"))

        return records
