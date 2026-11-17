"""Aws s3 wrapper."""

import asyncio
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import IO

from aiofiles.threadpool.binary import AsyncBufferedReader
from loguru import logger
from pydantic import Field

from aws_helpers.client import AwsClient, AwsClientConfiguration
from aws_helpers.utils import (
    SPOOL_MAX_SIZE,
    AsyncReader,
    async_gzip_open,
    is_gzip_compressed,
)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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

    @staticmethod
    def _rewind_and_detect_gzip(content: IO[bytes]) -> tuple[int, bool]:
        """
        Rewind the downloaded content and check if it is gzip compressed.

        Args:
            content: IO[bytes]: the content, positioned at its end

        Returns:
            tuple[int, bool]: the size of the content and whether it is gzip compressed
        """
        size = content.tell()
        content.seek(0)
        compressed = is_gzip_compressed(content.read(2))
        content.seek(0)
        return size, compressed

    @asynccontextmanager
    async def read_key(
        self,
        key: str,
        bucket: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
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

        with tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE) as content:
            async with self.get_client("s3") as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)
                # entering the body yields the aiohttp response, which cannot read a given amount: read the body
                body = response["Body"]
                async with body:
                    while chunk := await body.read(DOWNLOAD_CHUNK_SIZE):
                        content.write(chunk)

            # the S3 client is closed here: no connection is held while the content is parsed
            size, compressed = self._rewind_and_detect_gzip(content)
            logger.info(f"Read {size} bytes{' (gzip)' if compressed else ''} from object {key}")

            if compressed:
                async_reader = await async_gzip_open(content, loop=loop)
            else:
                async_reader = AsyncBufferedReader(content, loop=loop, executor=None)
            try:
                yield async_reader
            finally:
                await async_reader.close()

    async def list_objects(
        self,
        bucket: str | None = None,
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
