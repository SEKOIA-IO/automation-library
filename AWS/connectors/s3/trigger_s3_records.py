"""Contains AwsS3RecordsTrigger."""
import orjson

from connectors.s3 import AbstractAwsS3QueuedConnector


class AwsS3RecordsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3RecordsTrigger."""

    name = "AWS S3 Records"

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse contents.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        if len(content) == 0:
            return []

        records = []
        for record in orjson.loads(content).get("Records", []):
            if record:
                records.append(record)

        return records
