"""Tests related to AwsS3ParquetRecordsTrigger."""

import io
from os import path
from pathlib import Path
from typing import Any

import aiofiles
import orjson
import pandas
import pyarrow
import pyarrow.parquet
import pytest

from connectors import AwsModule
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3 import AwsS3QueuedConfiguration
from connectors.s3.trigger_s3_flowlogs_parquet import AwsS3FlowLogsParquetRecordsTrigger
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_queued_config: AwsS3QueuedConfiguration,
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

    return connector


@pytest.mark.asyncio
async def test_aws_s3_flowlogs_records_trigger_parse_content(connector: AwsS3FlowLogsParquetRecordsTrigger):
    """
    Test AwsS3ParquetRecordsTrigger `_parse_content`.

    Args:
        connector: AwsS3RecordsTrigger
    """
    current_dir = path.dirname(__file__)
    with open(current_dir + "/test_parquet_result.json", "rb") as f:
        expected_result = orjson.loads(f.read())

    async with aiofiles.open(f"{current_dir}/test_parquet.parquet", "rb") as f:
        assert await async_list(connector._parse_content(f)) == expected_result


@pytest.mark.asyncio
async def test_aws_s3_flowlogs_records_trigger_parse_empty_data(connector: AwsS3FlowLogsParquetRecordsTrigger):
    async with async_temporary_file(b"") as f:
        assert await async_list(connector._parse_content(f)) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("row_count", [0, 1, 1000, 1001, 2501])
async def test_parse_content_converts_bounded_batches(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
    monkeypatch: pytest.MonkeyPatch,
    row_count: int,
) -> None:
    """Preserve full-file output and discarded counts while bounding Python conversion."""
    table = pyarrow.table(
        {
            "srcaddr": ["8.8.8.8" if i % 2 else "10.0.0.1" for i in range(row_count)],
            "dstaddr": ["10.0.0.2"] * row_count,
            "packets": [None if i % 3 == 0 else i for i in range(row_count)],
        }
    )
    buffer = io.BytesIO()
    pyarrow.parquet.write_table(table, buffer, row_group_size=700)
    content = buffer.getvalue()
    # Use the previous implementation as the output compatibility reference,
    # including pandas' nullable numeric conversion and JSON serialization.
    records = pandas.read_parquet(io.BytesIO(content)).to_dict(orient="records")
    expected = [
        orjson.dumps(record).decode("utf-8")
        for record in records
        if not connector.check_all_ips_are_private(record, ("srcaddr", "dstaddr"))
    ]
    discarded = DISCARDED_EVENTS.labels(intake_key=connector.configuration.intake_key)
    discarded_before = discarded._value.get()
    converted_sizes: list[int] = []
    original_to_dict = pandas.DataFrame.to_dict

    def track_conversion(frame: pandas.DataFrame, *args: Any, **kwargs: Any) -> Any:
        converted_sizes.append(len(frame))
        return original_to_dict(frame, *args, **kwargs)

    monkeypatch.setattr(pandas.DataFrame, "to_dict", track_conversion)
    async with async_temporary_file(content) as stream:
        assert await async_list(connector._parse_content(stream)) == expected

    assert converted_sizes == [1000] * (row_count // 1000) + ([row_count % 1000] if row_count % 1000 else [])
    assert discarded._value.get() - discarded_before == row_count - len(expected)


@pytest.mark.asyncio
async def test_parse_content_does_not_convert_later_batches_before_yielding(
    connector: AwsS3FlowLogsParquetRecordsTrigger, monkeypatch: pytest.MonkeyPatch
) -> None:
    table = pyarrow.table({"srcaddr": ["8.8.8.8"] * 2501, "dstaddr": ["10.0.0.1"] * 2501})
    buffer = io.BytesIO()
    pyarrow.parquet.write_table(table, buffer)
    converted_sizes: list[int] = []
    original_to_dict = pandas.DataFrame.to_dict

    def track_conversion(frame: pandas.DataFrame, *args: Any, **kwargs: Any) -> Any:
        converted_sizes.append(len(frame))
        return original_to_dict(frame, *args, **kwargs)

    monkeypatch.setattr(pandas.DataFrame, "to_dict", track_conversion)
    async with async_temporary_file(buffer.getvalue()) as stream:
        events = connector._parse_content(stream)
        try:
            assert orjson.loads(await anext(events)) == {"srcaddr": "8.8.8.8", "dstaddr": "10.0.0.1"}
            assert converted_sizes == [1000]
        finally:
            await events.aclose()


@pytest.mark.asyncio
async def test_parse_content_rejects_invalid_parquet(connector: AwsS3FlowLogsParquetRecordsTrigger) -> None:
    async with async_temporary_file(b"not a parquet file") as stream:
        with pytest.raises(pyarrow.ArrowInvalid):
            await async_list(connector._parse_content(stream))
