"""Contains AwsS3FlowLogsTrigger."""

import ipaddress
from itertools import islice

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

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse content from S3 bucket.

        Args:
            content: bytes

        Returns:
            list:
        """
        records = [
            record
            for record in content.decode("utf-8").split(self.configuration.separator)
            if len(record) > 0 and not self.check_all_ips_are_private(record)
        ]

        if self.configuration.ignore_comments:  # pragma: no cover
            records = [record for record in records if not record.strip().startswith("#")]

        return list(islice(records, self.configuration.skip_first, None))
