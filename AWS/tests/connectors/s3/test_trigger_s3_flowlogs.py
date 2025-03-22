"""Tests related to AwsS3FlowLogsTrigger."""

from pathlib import Path

import pytest
from faker import Faker

from connectors import AwsModule
from connectors.s3.trigger_s3_flowlogs import AwsS3FlowLogsConfiguration, AwsS3FlowLogsTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def test_data() -> bytes:
    return """
version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status

2 111111111111 eni-0a479835a7588c9ca 79.124.62.82 172.31.39.167 58757 39045 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 172.31.39.167 172.31.39.169 44789 123 17 1 76 1645469669 1645469724 ACCEPT OK
2 111111111111 eni-0a479835a7588c9ca 45.79.182.177 172.31.39.167 61000 465 6 1 40 1645469669 1645469724 REJECT OK
2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK
# 2 111111111111 eni-0a479835a7588c9ca 188.114.116.1 172.31.39.167 123 44789 17 1 76 1645469669 1645469724 ACCEPT OK

""".encode(
        "utf-8"
    )


@pytest.fixture
def aws_s3_flowlogs_trigger_config(faker: Faker) -> AwsS3FlowLogsConfiguration:
    """
    Create a configuration.

    Args:
        faker: Faker

    Returns:
        AwsS3LogsConfiguration:
    """
    config = {
        "frequency": 0,
        "queue_name": faker.word(),
        "separator": "\n",
        "skip_first": 1,
        "ignore_comments": True,
        "intake_key": faker.word(),
    }

    return AwsS3FlowLogsConfiguration(**config)


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_flowlogs_trigger_config: AwsS3FlowLogsConfiguration,
) -> AwsS3FlowLogsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_flowlogs_trigger_config: AwsS3FlowLogsConfiguration

    Returns:
        AwsS3ParquetRecordsTrigger:
    """
    connector = AwsS3FlowLogsTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_flowlogs_trigger_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_data(connector: AwsS3FlowLogsTrigger, test_data: bytes):
    """
    Test AwsS3FlowLogsTrigger `_parse_data`.

    Args:
        connector: AwsS3FlowLogsTrigger
        test_data: bytes
    """

    async with async_temporary_file(test_data) as f:

        assert (
            await async_list(connector._parse_content(f))
            == [
                line
                for line in test_data.decode("utf-8").split("\n")
                if line != "" and not line.startswith("#") and not connector.check_all_ips_are_private(line)
            ][connector.configuration.skip_first :]
        )


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_empty_data(connector: AwsS3FlowLogsTrigger):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []
