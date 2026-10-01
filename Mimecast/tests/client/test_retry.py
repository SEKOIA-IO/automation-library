from datetime import datetime, timedelta

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
