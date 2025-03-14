"""Contains AwsS3LogsTrigger."""

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

    async def _process_content(self, content: bytes) -> int:
        """
        Parse the content of the object and return a list of records.

        Args:
            content:

        Returns:
            list[str]:
        """
        records = []
        total_count = 0
        is_first = True
        for record in content.decode("utf-8").split(self.configuration.separator):
            if len(record) == 0:
                continue

            if self.configuration.skip_first and is_first:
                is_first = False
                continue

            is_first = False

            if self.configuration.ignore_comments and record.strip().startswith("#"):
                continue

            records.append(record)

            if len(records) >= self.limit_of_events_to_push:
                total_count += len(await self.push_data_to_intakes(events=records))
                records = []

        if records:
            total_count += len(await self.push_data_to_intakes(events=records))

        return total_count
