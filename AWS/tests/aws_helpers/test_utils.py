"""Test utils module."""

import io
from gzip import compress
from unittest.mock import MagicMock

import aiofiles
import pytest
from faker import Faker

from aws_helpers.utils import (
    PeekableStreamReader,
    async_gzip_open,
    async_islice,
    get_content,
    is_gzip_compressed,
    is_parquet_content,
    normalize_s3_key,
    unescape_string,
    split_stream_by_separator,
)
from tests.helpers import async_temporary_file


def test_normalize_s3_key():
    """Test normalize_s3_key function."""
    data_1 = "AWSLogs/CloudTrail/eu-west-2/2022/02/21/t_nTGkKkyO0OcwEIvv.json.gz"
    assert normalize_s3_key(data_1) == data_1

    data_2 = "aws-service%3Dvpcflowlogs/aws-region%3Deu-west-3/year%3D2022/month%3D09/day%3D15/test.parquet"
    expected_result_2 = "aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=09/day=15/test.parquet"
    assert normalize_s3_key(data_2) == expected_result_2


def test_get_content(session_faker: Faker):
    """
    Test get_content function.

    Args:
        session_faker: Faker
    """
    expected_result_1 = session_faker.word().encode()
    mock_1 = MagicMock()
    mock_1.read.return_value = expected_result_1
    data_1 = {
        "Body": mock_1,
    }

    assert get_content(data_1) == expected_result_1

    expected_result_2 = session_faker.word().encode()
    mock_2 = MagicMock()
    mock_2.read.return_value = compress(expected_result_2)
    data_2 = {
        "Body": mock_2,
    }

    assert get_content(data_2) == expected_result_2


def test_is_gzip_compressed():
    """Test is_gzip_compressed function."""
    gzip_content = b"\x1f\x8b\x08\x00\xae"
    parquet_content = b"PAR1\x15\x04\x15\x08\x150cbPAR1"

    assert is_gzip_compressed(b"") is False
    assert is_gzip_compressed(parquet_content) is False
    assert is_gzip_compressed(gzip_content) is True


def test_is_parquet_content():
    """Test is_parquet_content function."""
    parquet_content = b"PAR1\x15\x04\x15\x08\x150cbPAR1"
    not_parquet_content = b"PAR1\x15\x04\x15\x08\x150cb"

    assert is_parquet_content(b"") is False
    assert is_parquet_content(not_parquet_content) is False
    assert is_parquet_content(parquet_content) is True


@pytest.mark.asyncio
async def test_async_gzip_reader():
    content = b"data"
    async with aiofiles.tempfile.NamedTemporaryFile("wb+") as f:
        await f.write(compress(content))
        await f.seek(0)

        reader = await async_gzip_open(io.BytesIO(await f.read()))
        assert await reader.read() == content


def test_unescape_separator():
    test_1 = "\\r\\n\\t,"
    assert unescape_string(test_1) == "\r\n\t,"

    # Need to be backward compatible - we had literal values before
    test_2 = "\r\n\t,"
    assert unescape_string(test_2) == "\r\n\t,"


@pytest.mark.asyncio
async def test_peekable_stream_reader():
    content = b"data"
    async with async_temporary_file(content) as f:
        reader = PeekableStreamReader(f)

        # Test peek
        peeked_content = await reader.peek(len(content))
        assert peeked_content == content
        assert await reader.peek(1) == content[0:1]  # Ensure peek doesn't consume

        # Test read
        read_content = await reader.read(len(content))
        assert read_content == content

        # Test that the stream is now at the end
        assert await reader.read(1) == b""


@pytest.mark.parametrize(
    "content, expected_chunks",
    [
        (b"line1\nline2\nline3", [b"line1", b"line2", b"line3"]),
        (b"line1\nline2\nline3\n", [b"line1", b"line2", b"line3"]),
        (b"line1\nline2\nline3\n\n", [b"line1", b"line2", b"line3", b""]),
    ],
)
@pytest.mark.asyncio
async def test_split_stream_by_separator(content, expected_chunks):
    async with async_temporary_file(content) as f:
        chunks = []
        async for chunk in split_stream_by_separator(f, b"\n"):
            chunks.append(chunk)
        assert chunks == expected_chunks


@pytest.mark.parametrize(
    "items, start, stop, expected",
    [
        ([1, 2, 3, 4, 5], 0, None, [1, 2, 3, 4, 5]),
        ([1, 2, 3, 4, 5], 2, None, [3, 4, 5]),
        ([1, 2, 3, 4, 5], 0, 3, [1, 2, 3]),
        ([1, 2, 3, 4, 5], 2, 4, [3, 4]),
        ([1, 2, 3, 4, 5], 10, None, []),
        ([1, 2, 3, 4, 5], 0, 0, []),
        ([], 0, None, []),
    ],
)
@pytest.mark.asyncio
async def test_async_islice(items, start, stop, expected):
    """Test async_islice function."""

    async def async_iterable():
        for item in items:
            yield item

    result = [item async for item in async_islice(async_iterable(), start, stop)]
    assert result == expected
