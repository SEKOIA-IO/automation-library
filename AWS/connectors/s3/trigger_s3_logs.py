"""Contains AwsS3LogsTrigger."""
from itertools import islice

from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration


class AwsS3LogsConfiguration(AwsS3QueuedConfiguration):
    """AwsS3LogsTrigger configuration."""

    ignore_comments: bool = False
    skip_first: int = 0
    separator: str


class AwsS3LogsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3LogsTrigger."""

    configuration: AwsS3LogsConfiguration
    name = "AWS S3 Logs"

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse the content of the object and return a list of records.

        Args:
            content:

        Returns:
            list[str]:
        """
        records = [record for record in content.decode("utf-8").split(self.configuration.separator) if len(record) > 0]

        if self.configuration.ignore_comments:
            records = [record for record in records if not record.strip().startswith("#")]

        return list(islice(records, self.configuration.skip_first, None))
