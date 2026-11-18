"""Tests related to AwsS3ParquetRecordsTrigger."""

import gzip
import io
import tempfile
from contextlib import aclosing
from os import path
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiofiles
import orjson
import pandas
import pyarrow
import pyarrow.parquet
import pytest
from faker import Faker

from aws_helpers.utils import async_gzip_open, check_all_ips_are_private
from connectors import AwsModule
from connectors.metrics import DISCARDED_EVENTS
from connectors.s3.trigger_s3_flowlogs_parquet import (
    AwsS3FlowLogsParquetConfiguration,
    AwsS3FlowLogsParquetRecordsTrigger,
)
from tests.helpers import async_list, async_temporary_file


@pytest.fixture
def aws_s3_flowlogs_parquet_trigger_config(
    faker: Faker,
) -> AwsS3FlowLogsParquetConfiguration:
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
        "filter_internal_traffic": True,
    }

    return AwsS3FlowLogsParquetConfiguration(**config)


@pytest.fixture
def connector(
    aws_module: AwsModule,
    symphony_storage: Path,
    aws_s3_flowlogs_parquet_trigger_config: AwsS3FlowLogsParquetConfiguration,
) -> AwsS3FlowLogsParquetRecordsTrigger:
    """
    Create a connector.

    Args:
        aws_module: AwsModule
        symphony_storage: Path
        aws_s3_flowlogs_parquet_trigger_config: AwsS3FlowLogsParquetConfiguration

    Returns:
        AwsS3FlowLogsParquetRecordsTrigger:
    """
    connector = AwsS3FlowLogsParquetRecordsTrigger(module=aws_module, data_path=symphony_storage)

    connector.configuration = aws_s3_flowlogs_parquet_trigger_config

    return connector


@pytest.mark.asyncio
async def test_aws_s3_flowlogs_records_trigger_parse_content(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
):
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
async def test_aws_s3_flowlogs_records_trigger_parse_empty_data(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
):
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
        if not check_all_ips_are_private((record[name] for name in ("srcaddr", "dstaddr") if name in record))
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
            assert orjson.loads(await anext(events)) == {
                "srcaddr": "8.8.8.8",
                "dstaddr": "10.0.0.1",
            }
            assert converted_sizes == [1000]
        finally:
            await events.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_statistics", [True, False])
@pytest.mark.parametrize("integer_type", [pyarrow.int64(), pyarrow.uint64()])
@pytest.mark.parametrize("null_position", [0, 1000, None])
async def test_parse_content_preserves_file_wide_integer_serialization(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
    write_statistics: bool,
    integer_type: pyarrow.DataType,
    null_position: int | None,
) -> None:
    values: list[int | None] = [1] * 1001
    if null_position is not None:
        values[null_position] = None
    table = pyarrow.table(
        {
            "srcaddr": ["8.8.8.8"] * len(values),
            "dstaddr": ["10.0.0.1"] * len(values),
            "packets": pyarrow.array(values, type=integer_type),
        }
    )
    buffer = io.BytesIO()
    # Isolate the null in a different row group as well as a different batch.
    pyarrow.parquet.write_table(table, buffer, row_group_size=1000, write_statistics=write_statistics)
    content = buffer.getvalue()
    expected = [
        orjson.dumps(record).decode("utf-8")
        for record in pandas.read_parquet(io.BytesIO(content)).to_dict(orient="records")
    ]
    async with async_temporary_file(content) as stream:
        assert await async_list(connector._parse_content(stream)) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("write_statistics", [True, False])
@pytest.mark.parametrize("dtype", ["Int64", "UInt64"])
async def test_parse_content_preserves_explicit_pandas_integer_dtype(
    connector: AwsS3FlowLogsParquetRecordsTrigger, write_statistics: bool, dtype: str
) -> None:
    frame = pandas.DataFrame(
        {
            "srcaddr": ["8.8.8.8"] * 1001,
            "dstaddr": ["10.0.0.1"] * 1001,
            "packets": pandas.array([1] * 1000 + [None], dtype=dtype),
        }
    )
    buffer = io.BytesIO()
    frame.to_parquet(buffer, row_group_size=1000, write_statistics=write_statistics)
    content = buffer.getvalue()
    expected = [
        orjson.dumps(record).decode("utf-8")
        for record in pandas.read_parquet(io.BytesIO(content)).to_dict(orient="records")
    ]
    async with async_temporary_file(content) as stream:
        assert await async_list(connector._parse_content(stream)) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("write_statistics", [True, False])
@pytest.mark.parametrize("index_name", [None, "event_index"])
@pytest.mark.parametrize("dtype", ["Int64", "UInt64"])
async def test_parse_content_preserves_nullable_integer_index(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
    write_statistics: bool,
    index_name: str | None,
    dtype: str,
) -> None:
    frame = pandas.DataFrame(
        {
            "srcaddr": ["8.8.8.8"] * 1001,
            "dstaddr": ["10.0.0.1"] * 1001,
            "packets": [1] * 1001,
        },
        index=pandas.Index([1] * 1000 + [None], dtype=dtype, name=index_name),
    )
    buffer = io.BytesIO()
    frame.to_parquet(buffer, row_group_size=1000, write_statistics=write_statistics)
    content = buffer.getvalue()
    expected = [
        orjson.dumps(record).decode("utf-8")
        for record in pandas.read_parquet(io.BytesIO(content)).to_dict(orient="records")
    ]
    async with async_temporary_file(content) as stream:
        assert await async_list(connector._parse_content(stream)) == expected


@pytest.mark.asyncio
async def test_parse_content_skips_empty_record(
    connector: AwsS3FlowLogsParquetRecordsTrigger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the defensive empty-record guard without emitting or counting it."""
    buffer = io.BytesIO()
    pyarrow.parquet.write_table(pyarrow.table({"srcaddr": ["8.8.8.8"]}), buffer)
    discarded = DISCARDED_EVENTS.labels(intake_key=connector.configuration.intake_key)
    discarded_before = discarded._value.get()

    def empty_records(frame: pandas.DataFrame, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{}]

    monkeypatch.setattr(pandas.DataFrame, "to_dict", empty_records)
    async with async_temporary_file(buffer.getvalue()) as stream:
        assert await async_list(connector._parse_content(stream)) == []
    assert discarded._value.get() == discarded_before


@pytest.mark.parametrize(
    "record,expected",
    [
        ({"srcaddr": "10.0.0.1", "dstaddr": "192.168.1.1"}, True),
        ({"srcaddr": "8.8.8.8", "dstaddr": "10.0.0.1"}, False),
        ({"srcaddr": "invalid", "dstaddr": "10.0.0.1"}, True),
        ({"srcaddr": "invalid", "dstaddr": "8.8.8.8"}, False),
        ({"dstaddr": "8.8.8.8"}, False),
        ({}, True),
    ],
)
def test_check_all_ips_are_private(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
    record: dict[str, str],
    expected: bool,
) -> None:
    assert check_all_ips_are_private((record[name] for name in ("srcaddr", "dstaddr") if name in record)) is expected


@pytest.mark.asyncio
async def test_parse_content_rejects_invalid_parquet(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
) -> None:
    async with async_temporary_file(b"not a parquet file") as stream:
        with pytest.raises(pyarrow.ArrowInvalid):
            await async_list(connector._parse_content(stream))


@pytest.mark.asyncio
async def test_parse_content_closes_the_decompressed_spool_when_the_consumer_stops_early(
    connector: AwsS3FlowLogsParquetRecordsTrigger,
):
    table = pyarrow.table({"srcaddr": ["8.8.8.8"] * 3_000, "dstaddr": ["8.8.4.4"] * 3_000})
    parquet = io.BytesIO()
    pyarrow.parquet.write_table(table, parquet)
    stream = await async_gzip_open(io.BytesIO(gzip.compress(parquet.getvalue())))

    spools = []
    original_spool = tempfile.SpooledTemporaryFile

    def spy_spool(*args, **kwargs):
        spools.append(original_spool(*args, **kwargs))
        return spools[-1]

    with patch("aws_helpers.utils.stream.tempfile.SpooledTemporaryFile", side_effect=spy_spool):
        async with aclosing(connector._parse_content(stream)) as events:
            await anext(events)

    assert len(spools) == 1 and spools[0].closed
