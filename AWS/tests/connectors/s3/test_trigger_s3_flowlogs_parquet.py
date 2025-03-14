"""Tests related to AwsS3ParquetRecordsTrigger."""

from os import path
from pathlib import Path

import orjson
import pytest

from connectors import AwsModule
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_flowlogs_parquet import AwsS3FlowLogsParquetRecordsTrigger


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
    mock_push_data_to_intakes,
) -> AwsS3FlowLogsParquetRecordsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_queued_config: AwsS3QueuedConfiguration

    Returns:
        AwsS3FlowLogsParquetRecordsTrigger:
    """
    connector = AwsS3FlowLogsParquetRecordsTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_queued_config
    connector.push_data_to_intakes = mock_push_data_to_intakes

    return connector


@pytest.mark.asyncio
async def test_aws_s3_flowlogs_records_trigger_parse_content(connector: AwsS3FlowLogsParquetRecordsTrigger):
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

    assert await connector._process_content(parquet_data) == len(expected_result)
    assert await connector._process_content(b"") == 0
