"""Aws s3 client."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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

        logger.info(f"Reading object {key} from bucket {bucket}")

        async with self.get_client("s3") as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                data = await stream.read()

                yield data
