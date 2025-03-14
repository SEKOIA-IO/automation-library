"""Contains AwsS3FlowLogsTrigger."""

import ipaddress

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

    async def _process_content(self, content: bytes) -> int:
        """
        Parse content from S3 bucket.

        Args:
            content: bytes

        Returns:
            list:
        """
        records = []
        total_count = 0
        is_first = True

        for record in content.decode("utf-8").split(self.configuration.separator):
            if len(record) == 0:
                continue

            if self.configuration.ignore_comments and record.strip().startswith("#"):
                continue

            if not self.check_all_ips_are_private(record):
                # TODO: If test is wrong, we should move this line to the top of the loop or just delete it
                if self.configuration.skip_first and is_first:
                    is_first = False
                    continue

                is_first = False

                records.append(record)
                if len(records) >= self.limit_of_events_to_push:
                    total_count += len(await self.push_data_to_intakes(events=records))
                    records = []
            else:
                DISCARDED_EVENTS.labels(intake_key=self.configuration.intake_key).inc()

        if records:
            total_count += len(await self.push_data_to_intakes(events=records))

        return total_count
