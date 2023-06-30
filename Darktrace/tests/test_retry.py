from datetime import datetime, timedelta

from urllib3.response import HTTPResponse

from darktrace_modules.client.retry import Retry


def test_parse_ratelimit_retry_after():
    assert Retry().parse_ratelimit_retry_after("0") is None
    future = datetime.timestamp(datetime.utcnow() + timedelta(days=1))
    assert Retry().parse_ratelimit_retry_after(str(future)) is not None


def test_get_retry_after():
    future = datetime.timestamp(datetime.utcnow() + timedelta(days=1))

    response = HTTPResponse(headers={"Retry-After": str(int(future))})
    assert Retry().get_retry_after(response) is not None

    response = HTTPResponse(headers={"X-Rate-Limit-Reset": str(future)})
    assert Retry().get_retry_after(response) is not None

    response = HTTPResponse()
    assert Retry().get_retry_after(response) is None
