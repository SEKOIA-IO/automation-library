"""Aws s3 wrapper."""

import asyncio
import gzip
import io
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiofiles.threadpool.binary import AsyncBufferedReader
from loguru import logger
from pydantic.v1 import Field
from sekoia_automation.aio.helpers.aws.client import AwsClient, AwsConfiguration

from aws_helpers.utils import is_gzip_compressed, async_gzip_open, AsyncReader


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
    async def read_key(
        self, key: str, bucket: str | None = None, loop: asyncio.AbstractEventLoop | None = None
    ) -> AsyncGenerator[AsyncReader, None]:
        """
        Reads text file from S3 bucket.

        Args:
            key: str
            bucket: str | None: if not provided, then use default bucket from configuration

        Yields:
            str:
        """
        bucket = bucket or self._configuration.bucket

        if loop is None:
            loop = asyncio.get_running_loop()

        logger.info(f"Reading object {key} from bucket {bucket}")

        async with self.get_client("s3") as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                content = io.BytesIO(await stream.read())
                if is_gzip_compressed(content.getbuffer()):
                    yield await async_gzip_open(content, loop=loop)
                else:
                    yield AsyncBufferedReader(content, loop=loop, executor=None)
