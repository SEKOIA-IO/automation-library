"""Tests related to AwsS3FlowLogsTrigger."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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

""".encode("utf-8")


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


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_parquet_data(connector: AwsS3FlowLogsTrigger):
    # Include invalid UTF-8 bytes to ensure text decoding is never attempted.
    parquet_content = b"PAR1\xc2\x15\x04\x15\x08\x150cbPAR1"
    connector.log = MagicMock()

    async with async_temporary_file(parquet_content) as f:
        assert await async_list(connector._parse_content(f)) == []

    connector.log.assert_called_once_with(
        message=(
            "Parquet content detected in AWS S3 Flow Logs text trigger. "
            "Use the AWS S3 Parquet records trigger (Fetch new FlowLogs Parquet records on S3) "
            "for .parquet objects."
        ),
        level="warning",
    )


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_parse_record_spanning_read_chunks(connector: AwsS3FlowLogsTrigger):
    """Records crossing the read chunk boundary are returned whole."""
    records = [
        f"2 111111111111 eni-0a479835a7588c9ca 79.124.62.{i % 250 + 1} 172.31.39.167 {i} 39045 6 1 40 1 2 REJECT OK"
        for i in range(30)
    ]
    connector.configuration.ignore_comments = False
    connector.configuration.skip_first = 0

    with patch("connectors.s3.trigger_s3_flowlogs.READ_CHUNK_SIZE", 64):
        async with async_temporary_file("\n".join(records).encode("utf-8")) as f:
            assert await async_list(connector._parse_content(f)) == records


@pytest.mark.asyncio
async def test_aws_s3_logs_trigger_never_reads_whole_object(connector: AwsS3FlowLogsTrigger, test_data: bytes):
    """The object is read by bounded chunks, never in one go."""
    sizes = []

    class BoundedReader:
        def __init__(self, data: bytes):
            self._data = data

        async def read(self, size: int = -1) -> bytes:
            sizes.append(size)
            assert size > 0, "the whole object must not be read at once"
            chunk, self._data = self._data[:size], self._data[size:]
            return chunk

    assert await async_list(connector._parse_content(BoundedReader(test_data))) != []
    assert sizes
