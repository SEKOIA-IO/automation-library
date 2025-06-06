from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

import requests


@dataclass
class ApiError:
    status_code: int
    reason: str
    id: str = "N/A"
    data: str = "N/A"
    message: str = "Unknown error"

    def __str__(self):
        return f"Request failed with status code {self.status_code} - {self.reason} - error id: {self.id} - error message: {self.message} - error data: {self.data}"

    @classmethod
    def from_response_error(cls, response: requests.Response):
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        return cls(
            status_code=response.status_code,
            reason=response.reason,
            id=error_data.get("error_id", "N/A"),
            data=error_data.get("error_data", "N/A"),
            message=error_data.get("error_message", "Unknown error"),
        )


def utc_zulu_format(dt: datetime) -> str:
    """Convert a datetime object to a UTC Zulu format string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_enum(base: type, name: str, values: set[str], methods: dict[str, Callable]) -> type:
    """
    Create an enum class with the specified base class and names.
    """
    klass = base(name, list((key.upper(), key) for key in values))

    for method_name, method in methods.items():
        setattr(klass, method_name, method)

    return klass
