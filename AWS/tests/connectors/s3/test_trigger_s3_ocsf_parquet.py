"""Tests related to AwsS3OcsfTrigger."""

from os import path
from pathlib import Path

import aiofiles
import orjson
import pytest

from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_ocsf_parquet import AwsS3OcsfTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
) -> AwsS3OcsfTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_queued_config: AwsS3QueuedConfiguration

    Returns:
        AwsS3OcsfTrigger:
    """
    connector = AwsS3OcsfTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_queued_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_ocsf_trigger_parse_content(
    connector: AwsS3OcsfTrigger,
):
    """
    Test AwsS3OcsfTrigger `_parse_content`.

    Args:
        connector: AwsS3RecordsTrigger
    """
    current_dir = path.dirname(__file__)
    async with aiofiles.open(f"{current_dir}/test_ocsf.parquet", "rb") as f:
        assert await async_list(connector._parse_content(f)) != []


@pytest.mark.asyncio
async def test_aws_s3_ocsf_trigger_parse_empty_content(
    connector: AwsS3OcsfTrigger,
):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []


@pytest.fixture
def ocsf_file_notification() -> str:
    """
    Create a SQS message with necessary bucket and key.

    Args:
        test_bucket: str
        test_key: str

    Returns:
        str:
    """
    return """
{
  "source": "aws.s3",
  "time": "2021-11-12T00:00:00Z",
  "account": "123456789012",
  "region": "ca-central-1",
  "resources": [
    "arn:aws:s3:::amzn-s3-demo-bucket"
  ],
  "detail": {
    "bucket": {
      "name": "amzn-s3-demo-bucket"
    },
    "object": {
      "key": "example-key",
      "size": 5,
      "etag": "b57f9512698f4b09e608f4f2a65852e5"
    },
    "request-id": "N4N7GDK58NMKJ12R",
    "requester": "securitylake.amazonaws.com"
  }
}
"""


def test_aws_s3_ocsf_trigger_get_notification(
    connector: AwsS3OcsfTrigger,
    ocsf_file_notification: str,
):
    """
    Test AwsS3OcsfTrigger `_get_notifs_from_sqs_message`.

    Args:
        connector: AwsS3RecordsTrigger
    """

    notif = connector._get_notifs_from_sqs_message(ocsf_file_notification)

    assert len(notif) == 1
    assert orjson.loads(ocsf_file_notification) == notif[0]


def test_aws_s3_ocsf_trigger_get_object_from_notification(
    connector: AwsS3OcsfTrigger,
    ocsf_file_notification: str,
):
    """
    Test AwsS3OcsfTrigger `_get_object_from_notification`.

    Args:
        connector: AwsS3RecordsTrigger
    """

    notif = orjson.loads(ocsf_file_notification)
    bucket_name, object_name = connector._get_object_from_notification(notif)

    assert bucket_name == "amzn-s3-demo-bucket"
    assert object_name == "example-key"
