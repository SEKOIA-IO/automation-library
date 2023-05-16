"""Test S3 wrapper."""
from unittest.mock import AsyncMock, patch

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

    # Prepare the mocked response
    expected_data = session_faker.sentence().encode("utf-8")
    mocked_response = {"Body": AsyncMock(read=AsyncMock(return_value=expected_data))}

    with patch("aws.s3.boto3.client") as mock_client:
        # Mock the get_object method of the client
        mock_s3 = mock_client.return_value
        mock_s3.get_object.return_value = mocked_response

        # Create the S3Wrapper instance
        configuration = S3Configuration(
            aws_access_key_id=session_faker.word(),
            aws_secret_access_key=session_faker.word(),
            aws_region=session_faker.word(),
        )

        wrapper = S3Wrapper(configuration)

        # Call the read_key method
        async with wrapper.read_key(key, bucket) as file_data:
            # Assert the data returned matches the expected content
            assert await file_data == expected_data

        # Assert that the get_object method was called with the correct arguments
        mock_s3.get_object.assert_called_once_with(Bucket=bucket, Key=key)
