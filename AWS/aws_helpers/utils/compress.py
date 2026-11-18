import gzip
from typing import Any


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
