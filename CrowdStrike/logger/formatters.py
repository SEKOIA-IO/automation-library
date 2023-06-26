"""Set of formatter functions."""

from pprint import pformat
from typing import Any


def format_record(record: dict[Any, Any], loguru_format: str) -> str:
    """
    Format loguru_format based on record.

    Use pformat for log any data like request/response body during debug.
    Work with logging if loguru handle it.
    Example:
    >>> payload = [{"users":[{"name": "Nick", "age": 87, "is_active": True}]
    >>> logger.bind(payload=).debug("users payload")
    >>> [
    >>>     {
    >>>         'count': 1,
    >>>         'users': [   {'age': 87, 'is_active': True, 'name': 'Nick'} ]
    >>>     }
    >>> ]

    Args:
        record: dict[any, any]
        loguru_format: str

    Returns:
        str: logging string
    """
    format_str = loguru_format
    if record["extra"].get("payload") is not None:
        record["extra"]["payload"] = pformat(
            record["extra"]["payload"],
            indent=4,
            compact=True,
        )
        format_str = "".join([loguru_format, "\n<level>{extra[payload]}</level>"])

    return "".join([format_str, "{exception}\n"])
