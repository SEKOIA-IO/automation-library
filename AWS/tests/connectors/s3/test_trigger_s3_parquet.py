"""Tests related to AwsS3ParquetRecordsTrigger."""
from os import path

import orjson
import pytest

from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_parquet import AwsS3ParquetRecordsTrigger


@pytest.fixture
def connector(
    aws_module: AwsModule,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
) -> AwsS3ParquetRecordsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        aws_s3_queued_config: AwsS3QueuedConfiguration

    Returns:
        AwsS3ParquetRecordsTrigger:
    """
    connector = AwsS3ParquetRecordsTrigger()

    connector.module = aws_module
    connector.configuration = aws_s3_queued_config

    return connector


def test_aws_s3_records_trigger_parse_content(connector: AwsS3ParquetRecordsTrigger):
    """
    Test AwsS3ParquetRecordsTrigger `_parse_content`.

    Args:
        connector: AwsS3RecordsTrigger
    """
    current_dir = path.dirname(__file__)
    with open(current_dir + "/test_parquet.parquet", "rb") as f:
        parquet_data = f.read()

    with open(current_dir + "/test_parquet_result.json", "rb") as f:
        expected_result = orjson.loads(f.read())

    assert connector._parse_content(parquet_data) == expected_result
    assert connector._parse_content(b"") == []
