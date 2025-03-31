import asyncio
import io
import gzip
from abc import abstractmethod
from concurrent.futures import Executor
from functools import partial
from typing import Any, BinaryIO, Protocol
from urllib.parse import unquote

from aiofiles.threadpool.binary import AsyncBufferedReader


def is_gzip_compressed(content: bytes) -> bool:
    """
    Check if the current object is compressed with gzip.

    Args:
        content: bytes

    Returns:
        bool:
    """
    # check the magic number
    return content[0:2] == b"\x1f\x8b"


def get_content(obj: dict[str, Any]) -> bytes:
    """
    Return the content of the object.

    Args:
        obj: dict[str, Any]

    Returns:
        bytes:
    """
    content: bytes = obj["Body"].read()

    if is_gzip_compressed(content):  # pragma: no cover
        content = gzip.decompress(content)

    return content


def normalize_s3_key(key: str) -> str:
    """
    Normalize S3 key.

    Args:
        key: str

    Returns:
        str:
    """
    return unquote(key)


class AsyncReader(Protocol):

    @abstractmethod
    async def read(self, size: int = -1, /) -> Any:
        return NotImplemented


async def async_gzip_open(
    file: BinaryIO,
    mode: str = "r",
    compresslevel: int = 9,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    executor: Executor | None = None,
) -> Any:
    if loop is None:
        loop = asyncio.get_running_loop()

    cb = partial(
        gzip.open,
        file,
        mode=mode,
        compresslevel=compresslevel,
        encoding=encoding,
        errors=errors,
        newline=newline,
    )
    f = await loop.run_in_executor(executor, cb)
    return AsyncBufferedReader(f, loop=loop, executor=executor)
