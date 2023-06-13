from typing import Any

import orjson

from aws.s3.base import AWSS3FetcherTrigger, AWSS3Worker


class CloudTrailLogsWorker(AWSS3Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _parse_content(self, content: bytes) -> list[dict[str, Any]]:
        return orjson.loads(content)["Records"]


class CloudTrailLogsTrigger(AWSS3FetcherTrigger):
    """
    The CloudTrail logs trigger reads the next batch of logs published on the S3 bucket
    and forward them to the playbook run.
    """

    name = "AWS CloudTrail"
    service = "cloudtrail"
    worker_class = CloudTrailLogsWorker
    prefix_pattern = "AWSLogs/{account_id}/CloudTrail/{region}/"
