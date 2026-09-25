import asyncio
import codecs
import gzip
from abc import abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable
from concurrent.futures import Executor
from functools import partial
from typing import Any, BinaryIO, Protocol, TypeVar
from urllib.parse import unquote

from aiofiles.threadpool.binary import AsyncBufferedReader

T = TypeVar("T")


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


def is_parquet_content(content: bytes) -> bool:
    """
    Check if the current object appears to be an Apache Parquet file.

    Args:
        content: bytes

    Returns:
        bool:
    """
    # Parquet files start and end with the magic bytes PAR1.
    return len(content) >= 8 and content[0:4] == b"PAR1" and content[-4:] == b"PAR1"


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


def unescape_string(escaped_str: str) -> str:
    """
    Converts literal escape sequences (like '\\n')
    into actual special characters.

    Args:
        escaped_str: str

    Returns:
        str:
    """
    return codecs.decode(escaped_str.encode("utf-8"), "unicode_escape")


class AsyncReader(Protocol):
    @abstractmethod
    async def read(self, size: int = -1, /) -> Any:
        return NotImplemented


class PeekableAsyncReader(Protocol):
    @abstractmethod
    async def peek(self, size: int, /) -> Any:
        return NotImplemented


# mypy: ignore-errors
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
    return AsyncBufferedReader(f, loop=loop, executor=executor)  # type: ignore[arg-type]


class PeekableStreamReader:
    """
    A wrapper around an AsyncReader that allows peeking at the next bytes without consuming them.
    """

    def __init__(self, stream: AsyncReader):
        """
        Initialize the PeekableStreamReader.

        Args:
            stream: AsyncReader
        """
        # underlying stream to read from
        self._stream = stream

        # buffer to hold peeked data
        self._buffer = b""

    async def read(self, size: int = -1) -> bytes:
        """
        Read bytes from the stream, consuming them.

        Args:
            size: int - The number of bytes to read. If -1, read until EOF.
        Returns:
            bytes: The bytes read from the stream.
        """
        # If size is -1, read all remaining data from the stream.
        if size == -1:
            data = await self._stream.read()
            return self._buffer + data

        # If the buffer has enough data, return it and clear the buffer.
        if len(self._buffer) >= size:
            result = self._buffer[:size]
            self._buffer = self._buffer[size:]
            return result

        # If the buffer doesn't have enough data, read the remaining bytes from the stream.
        data = await self._stream.read(size - len(self._buffer))
        result = self._buffer + data
        self._buffer = b""
        return result

    async def peek(self, size: int) -> bytes:
        """
        Peek at the next bytes in the stream without consuming them.

        Args:
            size: int - The number of bytes to peek at.
        Returns:
            bytes: The next bytes in the stream.
        """
        # If the buffer doesn't have enough data, read from the stream until we have enough.
        while len(self._buffer) < size:
            data = await self._stream.read(size - len(self._buffer))
            if not data:
                break
            self._buffer += data

        # Return the requested number of bytes from the buffer
        return self._buffer[:size]


async def async_islice(iterable: AsyncIterable[T], start: int, stop: int | None = None) -> AsyncGenerator[T, None]:
    """
    Async equivalent of itertools.islice, for async iterables.

    Args:
        iterable: AsyncIterable[T]
        start: int - The number of items to skip before yielding.
        stop: int | None - The index at which to stop yielding (exclusive). If None, yield until exhaustion.

    Returns:
        AsyncGenerator[T, None]: An async generator yielding items in the [start, stop) range.
    """
    index = 0
    async for item in iterable:
        if stop is not None and index >= stop:
            break

        if index >= start:
            yield item

        index += 1


async def split_stream_by_separator(
    stream: AsyncReader, separator: bytes, chunk_size: int = 1024
) -> AsyncGenerator[bytes, None]:
    """
    Split a stream into chunks based on a separator.

    Args:
        stream: AsyncReader
        separator: bytes

    Returns:
        AsyncGenerator[bytes, None]: An async generator yielding chunks of data.
    """
    buffer = b""
    while True:
        chunk = await stream.read(chunk_size)
        if not chunk:
            if buffer:
                yield buffer
            break

        buffer += chunk
        while True:
            index = buffer.find(separator)
            if index == -1:
                break
            yield buffer[:index]
            buffer = buffer[index + len(separator) :]
