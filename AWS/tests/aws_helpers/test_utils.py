"""Test utils module."""

import io
from gzip import compress
from unittest.mock import MagicMock

import aiofiles
import pytest
from faker import Faker

from aws_helpers.utils import async_gzip_open, get_content, is_gzip_compressed, normalize_s3_key


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


@pytest.mark.asyncio
async def test_async_gzip_reader():
    content = b"data"
    async with aiofiles.tempfile.NamedTemporaryFile("wb+") as f:
        await f.write(compress(content))
        await f.seek(0)

        reader = await async_gzip_open(io.BytesIO(await f.read()))
        assert await reader.read() == content
