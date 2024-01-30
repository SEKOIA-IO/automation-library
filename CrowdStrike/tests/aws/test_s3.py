"""Test S3 wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.s3 import S3Configuration, S3Wrapper


@pytest.mark.asyncio
async def test_read_key(session_faker):
    """
    Test read_key method.

    Args:
        session_faker:
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

    with patch("aws.s3.S3Wrapper.get_client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.get_object = AsyncMock()

        mock_client.return_value.__aenter__.return_value = mock_s3

        s3_response = {"Body": AsyncMock()}
        s3_response["Body"].__aenter__.return_value = s3_response["Body"]
        s3_response["Body"].read = AsyncMock(return_value=text.encode("utf-8"))

        mock_s3.get_object.return_value = s3_response

        async with s3.read_key(key) as content:
            assert content == text.encode("utf-8")

        # Assert that the S3 client methods were called with the correct arguments
        mock_client.assert_called_once_with("s3")
        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)
