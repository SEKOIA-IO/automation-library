"""
The CloudTrail logs trigger reads the next batch of logs published on the S3 bucket
and forward them to the playbook run.
"""

from typing import Any

import orjson

from .base import AwsS3FetcherTrigger, AwsS3Worker


class CloudTrailLogsWorker(AwsS3Worker):
    """Implementation of CloudTrailLogsWorker."""

    def _parse_content(self, content: bytes) -> list[dict[str, Any]]:
        """
        Parse content implementation.

        Args:
            content: bytes

        Returns:
            list[dict[str, Any]]:
        """
        result: list[dict[str, Any]] = orjson.loads(content).get("Records", [])

        return result


class CloudTrailLogsTrigger(AwsS3FetcherTrigger):
    """Initialize CloudTrailLogsTrigger"""

    name = "AWS CloudTrail"
    service = "cloudtrail"
    worker_class = CloudTrailLogsWorker
    prefix_pattern = "AWSLogs/{account_id}/CloudTrail/{region}/"
