from aws_helpers.utils.codecs import normalize_s3_key, unescape_string
from aws_helpers.utils.compress import is_gzip_compressed, get_content
from aws_helpers.utils.parquet import is_parquet_content
from aws_helpers.utils.stream import (
    AsyncReader,
    PeekableAsyncReader,
    async_gzip_open,
    PeekableStreamReader,
    async_islice,
    split_stream_by_separator,
)

__all__ = [
    "normalize_s3_key",
    "unescape_string",
    "is_gzip_compressed",
    "get_content",
    "is_parquet_content",
    "AsyncReader",
    "PeekableAsyncReader",
    "async_gzip_open",
    "PeekableStreamReader",
    "async_islice",
    "split_stream_by_separator",
]
