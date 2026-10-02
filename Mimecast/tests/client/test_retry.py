from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from urllib3.response import HTTPResponse

from mimecast_modules.client.retry import Retry


@pytest.mark.parametrize(
    "header_value,has_retry_after",
    [
        ("0", False),
        (str(datetime.timestamp(datetime.utcnow() + timedelta(days=1))), True),
    ],
)
def test_parse_ratelimit_retry_after(header_value: str, has_retry_after: bool) -> None:
    value = Retry().parse_ratelimit_retry_after(header_value)
    assert (value is not None) is has_retry_after


@pytest.mark.parametrize(
    "headers,has_retry_after",
    [
        ({"X-RateLimit-Reset": str(datetime.timestamp(datetime.utcnow() + timedelta(days=1)))}, True),
        ({}, False),
    ],
)
def test_get_retry_after(headers: dict[str, str], has_retry_after: bool) -> None:
    response = HTTPResponse(headers=headers)
    value = Retry().get_retry_after(response)

    assert (value is not None) is has_retry_after


def test_retry_increment_notifies_observer() -> None:
    observer = Mock()
    retry = Retry(total=1, retry_observer=observer)

    retry.increment(method="GET", url="https://example.test", error=Exception("boom"))

    observer.assert_called_once()


def test_retry_increment_without_observer() -> None:
    retry = Retry(total=1)
    next_retry = retry.increment(method="GET", url="https://example.test", error=Exception("boom"))

    assert isinstance(next_retry, Retry)
