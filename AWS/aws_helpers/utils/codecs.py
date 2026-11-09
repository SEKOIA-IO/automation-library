import codecs
from urllib.parse import unquote


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
