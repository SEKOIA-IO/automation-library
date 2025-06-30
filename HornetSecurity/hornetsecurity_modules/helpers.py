from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from cachetools import Cache, LRUCache
from sekoia_automation.storage import PersistentJSON


@dataclass
class ApiError:
    status_code: int
    reason: str
    id: str = "N/A"
    data: str = "N/A"
    message: str = "Unknown error"

    def __str__(self) -> str:
        return f"Request failed with status code {self.status_code} - {self.reason} - error id: {self.id} - error message: {self.message} - error data: {self.data}"

    @classmethod
    def from_response_error(cls, response: requests.Response) -> "ApiError":
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


def load_events_cache(context: PersistentJSON, maxsize: int = 1000) -> Cache[str, Any]:
    """
    Load the cache from the context
    """
    result: LRUCache[str, Any] = LRUCache(maxsize=maxsize)

    with context as cache:
        events_ids = cache.get("events_cache", [])

    for event_id in events_ids:
        result[event_id] = 1

    return result


def save_events_cache(events_cache: Cache[str, Any], context: PersistentJSON) -> None:
    """
    Save the cache to the context
    """
    with context as cache:
        cache["events_cache"] = list(events_cache.keys())


def remove_duplicates(
    events: list[dict[str, Any]], events_cache: Cache[str, Any], fieldname: str
) -> list[dict[str, Any]]:
    """
    Remove duplicates events from the fetched events and update the cache with new ids.

    Args:
        events: list[dict[str, Any]]

    Returns:
        list[dict[str, Any]]:
    """
    result = []

    # Iterate through the events and check if the event ID is already in the cache.
    for event in events:
        if event[fieldname] not in events_cache:
            result.append(event)
            events_cache[event[fieldname]] = True

    return result


def normalize_uri(uri: str) -> str:
    """
    Normalize a URI by ensuring it starts with "https://".
    """
    uri = uri.rstrip("/")  # Remove trailing slashes

    if uri.startswith("http://"):
        uri = uri.replace("http://", "https://", 1)

    if not uri.startswith("https://"):
        uri = f"https://{uri}"

    return uri


def range_offset_limit(offset: int, limit: int) -> Generator[tuple[int, int], None, None]:
    """
    Generate ranges of (offset, limit) pairs for pagination.

    Args:
        offset: The starting point for the range.
        limit: The number of items per page.

    Yields:
        tuple[int, int]: A tuple containing the offset and limit.
    """
    while True:
        yield offset, limit
        offset += limit


def has_more_emails(total_emails: int, offset: int, limit: int) -> bool:
    """
    Determine if there are more emails to fetch based on the total emails, the current offset and the limit.

    Args:
        total_emails: The total number of emails available.
        offset: The current offset in the email list.
        limit: The maximum number of emails to fetch in one request.

    Returns:
        bool: True if there are more emails to fetch, False otherwise.
    """
    return offset + limit < total_emails
