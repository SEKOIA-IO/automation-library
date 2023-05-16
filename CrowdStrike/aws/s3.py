"""Aws s3 client."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import boto3
from loguru import logger
from pydantic import Field

from .client import AwsClient, AwsConfiguration


class S3Configuration(AwsConfiguration):
    """AWS S3 wrapper configuration."""

    bucket: str | None = Field(default=None, description="AWS S3 bucket name")


class S3Wrapper(AwsClient[S3Configuration]):
    """Aws S3 wrapper."""

    def __init__(self, configuration: S3Configuration) -> None:
        """
        Initialize S3Wrapper.

        Args:
            configuration: AWS configuration
        """
        super().__init__(configuration)

        logger.info("Initializing s3 client")

        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=configuration.aws_access_key_id,
            aws_secret_access_key=configuration.aws_secret_access_key,
            region_name=configuration.aws_region,
        )

    @asynccontextmanager
    async def read_key(self, key: str, bucket: str | None = None) -> AsyncGenerator[bytes, None]:
        """
        Reads text file from S3 bucket.

        Args:
            key: str
            bucket: str | None: if not provided, then use default bucket from configuration

        Yields:
            str:
        """
        bucket = bucket or self._configuration.bucket

        logger.info("Reading object {0} from bucket {1}".format(key, bucket))

        try:
            response = self._s3.get_object(Bucket=bucket, Key=key)
            data = response["Body"].read()

            yield data
        finally:
            pass
