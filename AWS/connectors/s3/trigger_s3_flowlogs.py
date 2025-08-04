"""Contains AwsS3FlowLogsTrigger."""

import ipaddress
from collections.abc import AsyncGenerator
from itertools import islice

from aws_helpers.utils import AsyncReader
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import AbstractAwsS3QueuedConnector, AwsS3QueuedConfiguration


class AwsS3FlowLogsConfiguration(AwsS3QueuedConfiguration):
    """AwsS3FlowLogsTrigger configuration."""

    ignore_comments: bool = False
    skip_first: int = 0
    separator: str


class AwsS3FlowLogsTrigger(AbstractAwsS3QueuedConnector):
    """Implementation of AwsS3FlowLogsTrigger."""

    configuration: AwsS3FlowLogsConfiguration
    name = "AWS S3 Flow Logs"

    @staticmethod
    def check_all_ips_are_private(input_str: str) -> bool:
        """
        Check if all IPs in the input string are private

        Args:
            input_str: str

        Returns:
            bool:
        """
        ips = []
        for ip in input_str.split(" "):
            try:
                ips.append(ipaddress.ip_address(ip))
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

        records: list[str] = []
        for record in content.decode("utf-8").split(self.configuration.separator):
            if len(record) > 0:
                if not self.check_all_ips_are_private(record):
                    records.append(record)
                else:
                    DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

        if self.configuration.ignore_comments:  # pragma: no cover
            records = [record for record in records if not record.strip().startswith("#")]

        for record in list(islice(records, self.configuration.skip_first, None)):
            yield record
