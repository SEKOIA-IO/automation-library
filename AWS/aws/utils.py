from gzip import decompress
from typing import Any
from urllib.parse import unquote


def is_gzip_compressed(content: bytes) -> bool:
    """
    Check if the current object is compressed with gzip
    """
    # check the magic number
    return content[0:2] == b"\x1f\x8b"


def get_content(obj: dict[str, Any]) -> bytes:
    """
    Return the content of the object
    """
    content = obj["Body"].read()

    if is_gzip_compressed(content):  # pragma: no cover
        content = decompress(content)

    return content


def normalize_s3_key(key: str) -> str:
    """
    Normalize S3 key
    """
    return unquote(key)
