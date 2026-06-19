"""Test S3 wrapper."""

import datetime
import gzip
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dateutil.tz import tzutc
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


async def test_list_objects(session_faker: Faker):
    bucket = session_faker.word()
    prefix = "123/dnslogs/"
    marker = f"{prefix}2026-06-11/2026-06-10-11-35-1234.csv.gz"

    configuration = S3Configuration(
        aws_access_key_id=session_faker.word(),
        aws_secret_access_key=session_faker.word(),
        aws_region=session_faker.word(),
        bucket=bucket,
    )

    s3 = S3Wrapper(configuration)

    with patch("aws_helpers.s3_wrapper.S3Wrapper.get_client") as mock_client:
        mock_s3 = MagicMock()

        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value.__aiter__.return_value = [
            {
                "ResponseMetadata": {
                    "RequestId": "REQUEST_ID",
                    "HostId": "HOST_ID",
                    "HTTPStatusCode": 200,
                    "HTTPHeaders": {
                        "x-amz-id-2": "HOST_ID",
                        "x-amz-request-id": "REQUEST_ID",
                        "date": "Fri, 19 Jun 2026 10:31:38 GMT",
                        "x-amz-bucket-region": "eu-central-1",
                        "content-type": "application/xml",
                        "transfer-encoding": "chunked",
                        "server": "AmazonS3",
                    },
                    "RetryAttempts": 0,
                },
                "IsTruncated": False,
                "Contents": [
                    {
                        "Key": f"{prefix}2026-06-11/2026-06-11-12-40-8651.csv.gz",
                        "LastModified": datetime.datetime(2026, 6, 11, 12, 51, 28, tzinfo=tzutc()),
                        "ETag": '"E_TAG_1"',
                        "ChecksumAlgorithm": ["CRC64NVME"],
                        "ChecksumType": "FULL_OBJECT",
                        "Size": 201,
                        "StorageClass": "STANDARD",
                    },
                    {
                        "Key": f"{prefix}2026-06-11/2026-06-11-12-40-9621.csv.gz",
                        "LastModified": datetime.datetime(2026, 6, 11, 12, 51, 28, tzinfo=tzutc()),
                        "ETag": '"E_TAG_2"',
                        "ChecksumAlgorithm": ["CRC64NVME"],
                        "ChecksumType": "FULL_OBJECT",
                        "Size": 231,
                        "StorageClass": "STANDARD",
                    },
                    {
                        "Key": f"{prefix}2026-06-11/2026-06-11-12-40-cdba.csv.gz",
                        "LastModified": datetime.datetime(2026, 6, 11, 12, 51, 30, tzinfo=tzutc()),
                        "ETag": '"E_TAG_3"',
                        "ChecksumAlgorithm": ["CRC64NVME"],
                        "ChecksumType": "FULL_OBJECT",
                        "Size": 187,
                        "StorageClass": "STANDARD",
                    },
                    {
                        "Key": f"{prefix}2026-06-11/2026-06-11-12-40-fecd.csv.gz",
                        "LastModified": datetime.datetime(2026, 6, 11, 12, 51, 29, tzinfo=tzutc()),
                        "ETag": '"E_TAG_4"',
                        "ChecksumAlgorithm": ["CRC64NVME"],
                        "ChecksumType": "FULL_OBJECT",
                        "Size": 152,
                        "StorageClass": "STANDARD",
                    },
                ],
                "Name": bucket,
                "Prefix": prefix,
                "MaxKeys": 1000,
                "EncodingType": "url",
                "KeyCount": 4,
            }
        ]

        mock_client.return_value.__aenter__.return_value = mock_s3

        results = [obj async for obj in s3.list_objects(bucket=bucket, prefix=prefix, start_after=marker)]
        assert len(results) == 4
        mock_client.assert_called_once_with("s3")
        mock_s3.get_paginator.assert_called_once_with("list_objects_v2")
        mock_paginator.paginate.assert_called_once_with(Bucket=bucket, Prefix=prefix, StartAfter=marker)
