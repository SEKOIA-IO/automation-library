"""Contains AwsS3LogsTrigger."""

from collections.abc import AsyncGenerator
from itertools import islice

from aws_helpers.utils import AsyncReader
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

    async def _parse_content(self, stream: AsyncReader) -> AsyncGenerator[str, None]:
        """
        Parse content from S3 bucket.

        Args:
            stream: AsyncReader

        Returns:
             Generator:
        """
        content = await stream.read()

        records = [record for record in content.decode("utf-8").split(self.configuration.separator) if len(record) > 0]

        if self.configuration.ignore_comments:
            records = [record for record in records if not record.strip().startswith("#")]

        for record in list(islice(records, self.configuration.skip_first, None)):
            yield record
