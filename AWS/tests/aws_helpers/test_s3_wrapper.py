"""Test S3 wrapper."""

import gzip
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faker import Faker

from aws_helpers.s3_wrapper import S3Configuration, S3Wrapper


@pytest.mark.asyncio
async def test_read_key(session_faker: Faker):
    """
    Test read_key method.

    Args:
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="txt")
    bucket = session_faker.word()
    text = session_faker.sentence()

    configuration = S3Configuration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
        bucket=bucket,
    )

    s3 = S3Wrapper(configuration)

    with patch("aws_helpers.s3_wrapper.S3Wrapper.get_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.get_object = AsyncMock()

        mock_client.return_value.__aenter__.return_value = mock_s3

        s3_response = {"Body": AsyncMock()}
        s3_response["Body"].__aenter__.return_value = s3_response["Body"]
        s3_response["Body"].read = AsyncMock(return_value=text.encode("utf-8"))

        mock_s3.get_object.return_value = s3_response

        async with s3.read_key(key) as stream:
            assert await stream.read() == text.encode("utf-8")

        # Assert that the S3 client methods were called with the correct arguments
        mock_client.assert_called_once_with("s3")
        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)


@pytest.mark.asyncio
async def test_read_compressed_encoding_key(session_faker: Faker):
    """
    Test read_key method.

    Args:
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="txt")
    bucket = session_faker.word()
    text = session_faker.sentence()

    configuration = S3Configuration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
        bucket=bucket,
    )

    s3 = S3Wrapper(configuration)

    with patch("aws_helpers.s3_wrapper.S3Wrapper.get_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.get_object = AsyncMock()

        mock_client.return_value.__aenter__.return_value = mock_s3

        s3_response = {"Body": AsyncMock(), "ContentEncoding": "gzip"}
        s3_response["Body"].__aenter__.return_value = s3_response["Body"]
        s3_response["Body"].read = AsyncMock(return_value=gzip.compress(text.encode("utf-8")))

        mock_s3.get_object.return_value = s3_response

        async with s3.read_key(key) as stream:
            assert await stream.read() == text.encode("utf-8")

        # Assert that the S3 client methods were called with the correct arguments
        mock_client.assert_called_once_with("s3")
        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)


@pytest.mark.parametrize("content_type", ["application/gzip", "application/x-gzip"])
@pytest.mark.asyncio
async def test_read_compressed_content_key(session_faker: Faker, content_type: str):
    """
    Test read_key method.

    Args:
        session_faker: Faker
    """
    key = session_faker.file_path(depth=2, extension="txt")
    bucket = session_faker.word()
    text = session_faker.sentence()

    configuration = S3Configuration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
        bucket=bucket,
    )

    s3 = S3Wrapper(configuration)

    with patch("aws_helpers.s3_wrapper.S3Wrapper.get_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.get_object = AsyncMock()

        mock_client.return_value.__aenter__.return_value = mock_s3

        s3_response = {"Body": AsyncMock(), "ContentType": content_type}
        s3_response["Body"].__aenter__.return_value = s3_response["Body"]
        s3_response["Body"].read = AsyncMock(return_value=gzip.compress(text.encode("utf-8")))

        mock_s3.get_object.return_value = s3_response

        async with s3.read_key(key) as stream:
            assert await stream.read() == text.encode("utf-8")

        # Assert that the S3 client methods were called with the correct arguments
        mock_client.assert_called_once_with("s3")
        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)
