from itertools import islice
from typing import AsyncGenerator

from aws_helpers.utils import AsyncReader
from connectors.s3 import AbstractAwsS3ListConnector, AwsS3ListConfiguration, AwsS3LogsBaseConfiguration
from connectors.s3.provider import AwsAccountProvider
from connectors.s3.trigger_s3_logs import BaseAwsS3LogsTrigger


class AwsS3LogsNoSqsConfiguration(AwsS3ListConfiguration, AwsS3LogsBaseConfiguration):
    chunk_size: int = 1000
    ignore_comments: bool = False


class AwsS3LogsNoSqsTrigger(BaseAwsS3LogsTrigger, AbstractAwsS3ListConnector, AwsAccountProvider):
    """
    AWS S3 Logs Trigger that collects line-oriented records by listing the objects of a bucket.

    Unlike AwsS3LogsTrigger, this connector does not rely on SQS notifications. It lists the
    objects present in the bucket, reads each new object and uses a checkpoint (the key of the
    last processed object) to avoid reading the same file multiple times.
    """

    configuration: AwsS3LogsNoSqsConfiguration
    name = "AWS S3 Logs (no SQS)"
