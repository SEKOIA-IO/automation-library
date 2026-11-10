import asyncio
import gzip
import io
import shutil
import tempfile
from abc import abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable
from contextlib import asynccontextmanager
from concurrent.futures import Executor
from functools import partial
from typing import Any, BinaryIO, Protocol, TypeVar

from aiofiles.threadpool.binary import AsyncBufferedReader

T = TypeVar("T")

# objects bigger than this are spooled to a local temp file instead of memory
SPOOL_MAX_SIZE = 32 * 1024 * 1024

# a Parquet file starts and ends with these bytes
PARQUET_MAGIC = b"PAR1"


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
            result = self._buffer + data
            self._buffer = b""
            return result

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
    if start < 0 or (stop is not None and stop < 0):
        raise ValueError("start and stop must be non-negative integers")

    index = 0
    iterator = aiter(iterable)
    while stop is None or index < stop:
        try:
            item = await anext(iterator)
        except StopAsyncIteration:
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
    # if a separator is not supplied, default to b' '
    if not separator:
        separator = b" "

    buffer = bytearray()
    # position from which the next search starts: what lies before it is known to hold no separator
    search_from = 0
    while True:
        chunk = await stream.read(chunk_size)

        # If the chunk is empty, no more data to read. Yield any remaining buffer and exit.
        if not chunk:
            if buffer:
                yield bytes(buffer)
            break

        buffer += chunk
        start = 0
        while (index := buffer.find(separator, search_from)) != -1:
            yield bytes(buffer[start:index])
            start = search_from = index + len(separator)

        # drop the consumed records at once instead of copying the rest of the buffer for each of them
        del buffer[:start]
        # a separator may span two reads: only its possible beginning is searched again
        search_from = max(0, len(buffer) - len(separator) + 1)


async def _decompress_to_spool(file: gzip.GzipFile) -> BinaryIO:
    """
    Decompress a gzip file once into a spool (memory up to SPOOL_MAX_SIZE, then a temporary file).

    The copy runs in a thread, so that a big object does not block the event loop. A thread cannot be
    cancelled: it is waited for, however many times the task is cancelled, so that the files it uses are not
    closed under it. The spool is closed if the copy does not complete.

    Args:
        file: gzip.GzipFile

    Returns:
        BinaryIO: The spool, rewound to its beginning.
    """
    spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE)
    copy = asyncio.ensure_future(asyncio.to_thread(shutil.copyfileobj, file, spool))
    try:
        await asyncio.shield(copy)
    except (asyncio.CancelledError, Exception):
        while not copy.done():
            try:
                await asyncio.wait([copy])
            except asyncio.CancelledError:
                pass
        spool.close()
        raise

    spool.seek(0)
    # shortcut: the spool is closed (and its temp file removed) when garbage collected
    return spool  # type: ignore[return-value]


async def to_seekable_file(stream: AsyncReader) -> BinaryIO:
    """
    Return a seekable synchronous file for the stream, without copying it when possible.

    Args:
        stream: AsyncReader

    Returns:
        BinaryIO: The underlying file of an aiofiles reader, or an in-memory copy of the stream.
    """
    # aiofiles readers (as produced by S3Wrapper.read_key) wrap a sync file
    file = getattr(stream, "_file", None)
    if isinstance(file, gzip.GzipFile):
        # seeking backward in a gzip stream decompresses it again: decompress once into a spool
        return await _decompress_to_spool(file)

    if file is not None and file.seekable():
        return file  # type: ignore[no-any-return]

    # shortcut: other readers are copied in memory; only used by tests and non-aiofiles callers
    return io.BytesIO(await stream.read())


@asynccontextmanager
async def seekable_file(stream: AsyncReader) -> AsyncGenerator[BinaryIO, None]:
    """
    Yield a seekable synchronous file for the stream, and close it on exit if it was created for it.

    The underlying file of an aiofiles reader is owned by the reader and left open; a gzip object is decompressed
    into a new spool, which would otherwise live until it is garbage collected.

    Args:
        stream: AsyncReader

    Yields:
        BinaryIO: The seekable file.
    """
    file = await to_seekable_file(stream)
    try:
        yield file
    finally:
        if file is not getattr(stream, "_file", None):
            file.close()


async def has_parquet_footer(stream: Any) -> bool:
    """
    Check if a stream, already known to start with the Parquet magic bytes, also ends with them.

    The stream is rewound to read its end, then put back where it was.

    Args:
        stream: An aiofiles reader (as produced by S3Wrapper.read_key): it must support tell() and seek()

    Returns:
        bool: True if the stream is at least 8 bytes long and ends with the Parquet magic bytes.
    """
    position = await stream.tell()
    await stream.seek(0)
    try:
        async with seekable_file(stream) as file:
            size = file.seek(0, io.SEEK_END)
            if size < 2 * len(PARQUET_MAGIC):
                return False

            file.seek(size - len(PARQUET_MAGIC))
            return file.read(len(PARQUET_MAGIC)) == PARQUET_MAGIC
    finally:
        await stream.seek(position)
