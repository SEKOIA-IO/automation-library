"""
The Flowlog records trigger reads the next batch of logs published on the S3 bucket
and forward them to the playbook run.
"""

from .base import AwsS3FetcherTrigger, AwsS3Worker


class FlowlogRecordsWorker(AwsS3Worker):
    """Implementation of FlowlogRecordsWorker."""

    def _parse_content(self, content: bytes) -> list[str]:
        """
        Parse content implementation.

        Args:
            content: bytes

        Returns:
            list[str]:
        """
        return content.decode("utf-8").split("\n")[1:]


class FlowlogRecordsTrigger(AwsS3FetcherTrigger):
    """Implementation of FlowlogRecordsTrigger."""

    name = "AWS Flowlog"
    service = "ec2"
    worker_class = FlowlogRecordsWorker
    prefix_pattern = "AWSLogs/{account_id}/vpcflowlogs/{region}/"
