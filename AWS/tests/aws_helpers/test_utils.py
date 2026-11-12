"""Test utils module."""

import asyncio
import contextlib
import gzip
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from gzip import compress
from unittest.mock import AsyncMock, MagicMock, patch

import aiofiles
import pytest
from faker import Faker

from aws_helpers.utils import (
    PeekableStreamReader,
    async_gzip_open,
    async_islice,
    get_content,
    has_parquet_footer,
    seekable_file,
    is_gzip_compressed,
    is_parquet_content,
    normalize_s3_key,
    unescape_string,
    split_stream_by_separator,
    to_seekable_file,
)
from tests.helpers import async_temporary_file


def test_normalize_s3_key():
    """Test normalize_s3_key function."""
    data_1 = "AWSLogs/CloudTrail/eu-west-2/2022/02/21/t_nTGkKkyO0OcwEIvv.json.gz"
    assert normalize_s3_key(data_1) == data_1

    data_2 = "aws-service%3Dvpcflowlogs/aws-region%3Deu-west-3/year%3D2022/month%3D09/day%3D15/test.parquet"
    expected_result_2 = "aws-service=vpcflowlogs/aws-region=eu-west-3/year=2022/month=09/day=15/test.parquet"
    assert normalize_s3_key(data_2) == expected_result_2


def test_get_content(session_faker: Faker):
    """
    Test get_content function.

    Args:
        session_faker: Faker
    """
    expected_result_1 = session_faker.word().encode()
    mock_1 = MagicMock()
    mock_1.read.return_value = expected_result_1
    data_1 = {
        "Body": mock_1,
    }

    assert get_content(data_1) == expected_result_1

    expected_result_2 = session_faker.word().encode()
    mock_2 = MagicMock()
    mock_2.read.return_value = compress(expected_result_2)
    data_2 = {
        "Body": mock_2,
    }

    assert get_content(data_2) == expected_result_2


def test_is_gzip_compressed():
    """Test is_gzip_compressed function."""
    gzip_content = b"\x1f\x8b\x08\x00\xae"
    parquet_content = b"PAR1\x15\x04\x15\x08\x150cbPAR1"

    assert is_gzip_compressed(b"") is False
    assert is_gzip_compressed(parquet_content) is False
    assert is_gzip_compressed(gzip_content) is True


def test_is_parquet_content():
    """Test is_parquet_content function."""
    parquet_content = b"PAR1\x15\x04\x15\x08\x150cbPAR1"
    not_parquet_content = b"PAR1\x15\x04\x15\x08\x150cb"

    assert is_parquet_content(b"") is False
    assert is_parquet_content(not_parquet_content) is False
    assert is_parquet_content(parquet_content) is True


@pytest.mark.asyncio
async def test_async_gzip_reader():
    content = b"data"
    async with aiofiles.tempfile.NamedTemporaryFile("wb+") as f:
        await f.write(compress(content))
        await f.seek(0)

        reader = await async_gzip_open(io.BytesIO(await f.read()))
        assert await reader.read() == content


def test_unescape_separator():
    test_1 = "\\r\\n\\t,"
    assert unescape_string(test_1) == "\r\n\t,"

    # Need to be backward compatible - we had literal values before
    test_2 = "\r\n\t,"
    assert unescape_string(test_2) == "\r\n\t,"


@pytest.mark.asyncio
async def test_peekable_stream_reader():
    content = b"data"
    async with async_temporary_file(content) as f:
        reader = PeekableStreamReader(f)

        # Test peek
        peeked_content = await reader.peek(len(content))
        assert peeked_content == content
        assert await reader.peek(1) == content[0:1]  # Ensure peek doesn't consume

        # Test read
        read_content = await reader.read(len(content))
        assert read_content == content

        # Test that the stream is now at the end
        assert await reader.read(1) == b""


@pytest.mark.parametrize(
    "content, expected_chunks",
    [
        (b"line1\nline2\nline3", [b"line1", b"line2", b"line3"]),
        (b"line1\nline2\nline3\n", [b"line1", b"line2", b"line3"]),
        (b"line1\nline2\nline3\n\n", [b"line1", b"line2", b"line3", b""]),
    ],
)
@pytest.mark.asyncio
async def test_split_stream_by_separator(content, expected_chunks):
    async with async_temporary_file(content) as f:
        chunks = []
        async for chunk in split_stream_by_separator(f, b"\n", chunk_size=4):
            chunks.append(chunk)
        assert chunks == expected_chunks


@pytest.mark.parametrize(
    "content, separator, chunk_size, expected_chunks",
    [
        # separator spanning two reads
        (b"a\r\nb\r\nc", b"\r\n", 1, [b"a", b"b", b"c"]),
        (b"a\r\nb\r\nc", b"\r\n", 2, [b"a", b"b", b"c"]),
        (b"xabyabz", b"ab", 1, [b"x", b"y", b"z"]),
        # overlapping separator
        (b"aaa", b"aa", 1, [b"", b"a"]),
        # no separator in the data
        (b"abc", b"\n", 2, [b"abc"]),
        # empty separator falls back to a space
        (b"a b c", b"", 2, [b"a", b"b", b"c"]),
        # separator at the very start and at the very end
        (b"\nabc", b"\n", 3, [b"", b"abc"]),
        (b"abc\n", b"\n", 3, [b"abc"]),
        (b"", b"\n", 3, []),
    ],
)
@pytest.mark.asyncio
async def test_split_stream_by_separator_across_reads(content, separator, chunk_size, expected_chunks):
    async with async_temporary_file(content) as f:
        chunks = [chunk async for chunk in split_stream_by_separator(f, separator, chunk_size=chunk_size)]
        assert chunks == expected_chunks


@pytest.mark.parametrize(
    "items, start, stop, expected",
    [
        ([1, 2, 3, 4, 5], 0, None, [1, 2, 3, 4, 5]),
        ([1, 2, 3, 4, 5], 2, None, [3, 4, 5]),
        ([1, 2, 3, 4, 5], 0, 3, [1, 2, 3]),
        ([1, 2, 3, 4, 5], 2, 4, [3, 4]),
        ([1, 2, 3, 4, 5], 10, None, []),
        ([1, 2, 3, 4, 5], 0, 0, []),
        ([], 0, None, []),
    ],
)
@pytest.mark.asyncio
async def test_async_islice(items, start, stop, expected):
    """Test async_islice function."""

    async def async_iterable():
        for item in items:
            yield item

    result = [item async for item in async_islice(async_iterable(), start, stop)]
    assert result == expected


@pytest.mark.asyncio
async def test_to_seekable_file_returns_wrapped_file():
    async with async_temporary_file(b"data") as f:
        assert await to_seekable_file(f) is f._file


@pytest.mark.asyncio
async def test_to_seekable_file_copies_other_readers():
    stream = MagicMock()
    stream.read = AsyncMock(return_value=b"data")
    del stream._file

    file = await to_seekable_file(stream)

    assert isinstance(file, io.BytesIO)
    assert file.read() == b"data"


@pytest.mark.asyncio
async def test_to_seekable_file_decompresses_gzip_once():
    stream = await async_gzip_open(io.BytesIO(compress(b"data")))
    file = await to_seekable_file(stream)

    assert not isinstance(file, gzip.GzipFile)
    assert file.read() == b"data"


@pytest.mark.asyncio
async def test_to_seekable_file_decompresses_gzip_off_the_event_loop():
    loop_thread = threading.get_ident()
    copy_threads = []
    original_copyfileobj = shutil.copyfileobj

    def spy(*args, **kwargs):
        copy_threads.append(threading.get_ident())
        return original_copyfileobj(*args, **kwargs)

    stream = await async_gzip_open(io.BytesIO(compress(b"data")))
    with patch("aws_helpers.utils.stream.shutil.copyfileobj", side_effect=spy):
        file = await to_seekable_file(stream)

    assert copy_threads
    assert loop_thread not in copy_threads
    assert file.read() == b"data"


@pytest.mark.parametrize("cancellations", [1, 2])
@pytest.mark.asyncio
async def test_to_seekable_file_waits_for_the_copy_when_cancelled(cancellations):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    spools = []
    original_spool = tempfile.SpooledTemporaryFile

    def spy_spool(*args, **kwargs):
        spools.append(original_spool(*args, **kwargs))
        return spools[-1]

    def blocking_copy(*args, **kwargs):
        started.set()
        release.wait(5)
        finished.set()

    ended_before_release = []

    async def release_later():
        await asyncio.sleep(0.05)
        ended_before_release.append(task.done())
        release.set()

    stream = await async_gzip_open(io.BytesIO(compress(b"data")))
    with (
        patch("aws_helpers.utils.stream.tempfile.SpooledTemporaryFile", side_effect=spy_spool),
        patch("aws_helpers.utils.stream.shutil.copyfileobj", side_effect=blocking_copy),
    ):
        task = asyncio.create_task(to_seekable_file(stream))
        assert await asyncio.to_thread(started.wait, 5)
        for _ in range(cancellations):
            task.cancel()
            for _ in range(3):  # let the cancellation be delivered
                await asyncio.sleep(0)

        # the copy is released only after the task was cancelled: the task must still be waiting for it
        releaser = asyncio.create_task(release_later())
        with pytest.raises(asyncio.CancelledError):
            await task
        await releaser

    assert ended_before_release == [False]
    assert await asyncio.to_thread(finished.wait, 1)
    assert spools[0].closed


@pytest.mark.asyncio
async def test_to_seekable_file_closes_the_spool_when_the_copy_fails():
    spools = []
    original_spool = tempfile.SpooledTemporaryFile

    def spy_spool(*args, **kwargs):
        spools.append(original_spool(*args, **kwargs))
        return spools[-1]

    stream = await async_gzip_open(io.BytesIO(compress(b"data")))
    with (
        patch("aws_helpers.utils.stream.tempfile.SpooledTemporaryFile", side_effect=spy_spool),
        patch("aws_helpers.utils.stream.shutil.copyfileobj", side_effect=OSError("disk full")),
    ):
        with pytest.raises(OSError, match="disk full"):
            await to_seekable_file(stream)

    assert spools[0].closed


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"PAR1\xc2\x15cbPAR1", True),
        (b"PAR1PAR1", True),
        (b"PAR1PAR", False),
        (b"PAR1 text records\nsecond line\n", False),
        (b"PAR1\xc2\x15cb", False),
    ],
)
@pytest.mark.asyncio
async def test_has_parquet_footer_on_plain_stream(data, expected):
    async with async_temporary_file(data) as f:
        assert await f.read(4) == b"PAR1"  # what the caller consumed to recognize the header

        assert await has_parquet_footer(f) is expected

        # the stream is put back where it was and its file is still open
        assert await f.tell() == 4
        assert await f.read() == data[4:]
        assert not f._file.closed


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"PAR1\xc2\x15cbPAR1", True),
        (b"PAR1 text records\nsecond line\n", False),
        (b"PAR1PAR", False),
    ],
)
@pytest.mark.asyncio
async def test_has_parquet_footer_on_gzip_stream_closes_its_spool(data, expected):
    spools = []
    original_spool = tempfile.SpooledTemporaryFile

    def spy_spool(*args, **kwargs):
        spools.append(original_spool(*args, **kwargs))
        return spools[-1]

    stream = await async_gzip_open(io.BytesIO(compress(data)))
    assert await stream.read(4) == b"PAR1"

    with patch("aws_helpers.utils.stream.tempfile.SpooledTemporaryFile", side_effect=spy_spool):
        assert await has_parquet_footer(stream) is expected

    assert await stream.read() == data[4:]
    assert len(spools) == 1 and spools[0].closed


@pytest.mark.parametrize(
    "module",
    [
        "aws_helpers.utils",
        "connectors.s3.trigger_s3_logs",
        "connectors.s3.trigger_s3_records",
        "connectors.trigger_sqs_messages",
    ],
)
def test_shared_modules_do_not_load_pandas_or_pyarrow(module):
    """Importing the shared helpers and the non-Parquet connectors must not load pandas or pyarrow."""
    code = (
        f"import sys, importlib; importlib.import_module({module!r}); "
        "print('pandas' in sys.modules or 'pyarrow' in sys.modules)"
    )
    # run from the AWS root, whatever the directory pytest was started from
    aws_root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=aws_root)
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, 0),
        ("", 0),
        ("   ", 0),
        ("-1", 0),
        ("abc", 0),
        ("32MB", 0),
        ("1.5", 0),
        ("1e6", 0),
        ("0", 0),
        ("1048576", 1048576),
        (" 4096 ", 4096),
    ],
)
def test_spool_max_size_from_the_environment(value, expected):
    """AWS_SPOOL_MAX_SIZE is a number of bytes: anything that is not a non-negative integer counts as 0."""
    env = {key: val for key, val in os.environ.items() if key != "AWS_SPOOL_MAX_SIZE"}
    if value is not None:
        env["AWS_SPOOL_MAX_SIZE"] = value

    code = "from aws_helpers.utils import SPOOL_MAX_SIZE; print(SPOOL_MAX_SIZE)"
    aws_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=aws_root, env=env
    )
    assert result.stdout.strip() == str(expected)


@pytest.mark.asyncio
async def test_seekable_file_leaves_the_file_of_the_stream_open():
    async with async_temporary_file(b"data") as f:
        async with seekable_file(f) as file:
            assert file is f._file

        assert not f._file.closed


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.asyncio
async def test_seekable_file_closes_the_file_it_created(fail):
    stream = await async_gzip_open(io.BytesIO(compress(b"data")))

    with pytest.raises(RuntimeError) if fail else contextlib.nullcontext():
        async with seekable_file(stream) as file:
            assert file.read() == b"data"
            if fail:
                raise RuntimeError("parsing failed")

    assert file.closed
