"""Aws s3 wrapper."""

import asyncio
import io
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiofiles.threadpool.binary import AsyncBufferedReader
from loguru import logger
from pydantic import Field

from aws_helpers.client import AwsClient, AwsClientConfiguration
from aws_helpers.utils import AsyncReader, async_gzip_open, is_gzip_compressed


class S3Configuration(AwsClientConfiguration):
    """AWS S3 wrapper configuration."""

    bucket: str | None = Field(default=None, description="AWS S3 bucket name")


# mypy: ignore-errors
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
                with io.BytesIO(await stream.read()) as content:
                    if is_gzip_compressed(content.getbuffer()):
                        async_reader = await async_gzip_open(content, loop=loop)
                    else:
                        async_reader = AsyncBufferedReader(content, loop=loop, executor=None)
                    try:
                        yield async_reader
                    finally:
                        await async_reader.close()

    async def list_objects(
        self,
        bucket: str,
        prefix: str | None = None,
        start_after: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        List the objects available in a S3 bucket.

        The objects are returned in lexicographical order of their keys. The
        ``start_after`` parameter relies on the ``list_objects_v2`` ``StartAfter``
        option to only return the keys that are strictly greater than the marker,
        which allows the caller to implement a checkpoint and avoid reading the
        same object multiple times.
        """
        bucket = bucket or self._configuration.bucket

        kwargs: dict[str, str] = {"Bucket": bucket} if bucket else {}
        if prefix:
            kwargs["Prefix"] = prefix

        if start_after:
            kwargs["StartAfter"] = start_after

        logger.info(f"Listing objects from bucket {bucket}")

        async with self.get_client("s3") as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(**kwargs):
                for obj in page.get("Contents", []):
                    if obj.get("Size", 0) > 0:
                        yield obj
